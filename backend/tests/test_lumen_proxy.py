"""Afterglow browser proxy contracts for the extracted Lumen service."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient, Headers
from httpx import Request as HttpxRequest
from httpx import Response as HttpxResponse

from app.api.deps import get_token_info
from app.api.lumen import register_lumen
from app.main import app
from app.services.service_proxy import proxy, proxy_passthrough


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_token_info, None)


async def _authenticated(request: Request) -> dict:
    token_info = {
        "token": "caller-token",
        "project_id": "project-1",
        "user_id": "user-1",
        "username": "user",
        "roles": ["member"],
    }
    request.state.token_info = token_info
    return token_info


def _make_dummy_request(
    path: str = "/api/v1/chat/conversations",
    method: str = "GET",
    headers: dict[str, str] | None = None,
    query: str = "",
) -> Request:
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw_headers,
        "query_string": query.encode("latin-1"),
        "client": ("203.0.113.19", 54321),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_lumen_feature_gate_routes_inclusion():
    enabled_app = FastAPI()
    enabled_settings = SimpleNamespace(service_chat_enabled=True)
    assert register_lumen(enabled_app, enabled_settings) is True
    enabled_paths = {getattr(r, "path", "") for r in enabled_app.routes}
    assert "/api/v1/chat/mcp-oauth/callback" in enabled_paths
    assert "/api/v1/chat/{path:path}" in enabled_paths

    disabled_app = FastAPI()
    disabled_settings = SimpleNamespace(service_chat_enabled=False)
    assert register_lumen(disabled_app, disabled_settings) is False
    disabled_paths = {getattr(r, "path", "") for r in disabled_app.routes}
    assert not any(p.startswith("/api/v1/chat") for p in disabled_paths)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,upstream_path,body",
    [
        ("get", "/api/v1/chat/conversations", "/v1/conversations", None),
        ("post", "/api/v1/chat/conversations", "/v1/conversations", {"title": "New Chat"}),
        ("get", "/api/v1/chat/agents", "/v1/agents", None),
        ("delete", "/api/v1/chat/conversations/conv-1", "/v1/conversations/conv-1", None),
        ("get", "/api/v1/chat/workspaces", "/v1/workspaces", None),
        ("get", "/api/v1/chat/models", "/v1/chat/models", None),
    ],
)
async def test_browser_routes_proxy_to_lumen_service(api_client, method, path, upstream_path, body):
    app.dependency_overrides[get_token_info] = _authenticated
    forwarded = JSONResponse(status_code=200, content={"forwarded": True})
    with patch("app.api.lumen.proxy.proxy", new=AsyncMock(return_value=forwarded)) as proxy_call:
        call = getattr(api_client, method)
        response = await (call(path, json=body) if body is not None else call(path))

    assert response.status_code == 200
    assert response.json() == {"forwarded": True}
    service_type, request, upstream = proxy_call.await_args.args
    assert service_type == "lumen"
    assert upstream == upstream_path
    assert request.state.token_info["token"] == "caller-token"


@pytest.mark.asyncio
async def test_browser_proxy_requires_authentication(api_client):
    with patch("app.api.lumen.proxy.proxy", new=AsyncMock()) as proxy_call:
        response = await api_client.get("/api/v1/chat/conversations")

    assert response.status_code == 401
    proxy_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_lumen_mcp_oauth_callback_proxies_unauthenticated_with_cookies():
    req = _make_dummy_request(
        path="/api/v1/chat/mcp-oauth/callback",
        query="state=state-123&code=code-456",
        headers={"Cookie": "mcp_oauth_initiator_nonce=nonce-789"},
    )

    sent_requests: list[tuple[HttpxRequest, bool]] = []

    async def mock_send(outgoing_req: HttpxRequest, stream: bool = False):
        sent_requests.append((outgoing_req, stream))
        resp_headers = Headers(
            [
                ("location", "http://test/dashboard/chat?mcp_oauth=connected"),
                ("set-cookie", "cookie1=val1; Path=/"),
                ("set-cookie", "cookie2=val2; Path=/"),
            ]
        )
        resp = MagicMock(spec=HttpxResponse)
        resp.status_code = 303
        resp.headers = resp_headers
        resp.aiter_bytes = MagicMock()
        resp.aclose = AsyncMock()
        return resp

    mock_client = MagicMock()
    mock_client.build_request.side_effect = lambda method, url, headers, content: HttpxRequest(
        method, url, headers=headers, content=content
    )
    mock_client.send = AsyncMock(side_effect=mock_send)
    mock_client.aclose = AsyncMock()

    with patch("app.services.service_proxy.resolve_service_endpoint", return_value="http://lumen.internal"):
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await proxy_passthrough("lumen", req, "/v1/mcp-oauth/callback", forward_cookie=True)

    assert len(sent_requests) == 1
    sent_req, stream = sent_requests[0]
    assert str(sent_req.url) == "http://lumen.internal/v1/mcp-oauth/callback?state=state-123&code=code-456"
    assert sent_req.headers.get("cookie") == "mcp_oauth_initiator_nonce=nonce-789"
    assert sent_req.headers.get("x-forwarded-for") == "203.0.113.19"
    assert stream is True

    assert response.status_code == 303
    set_cookies = [val.decode("latin-1") for name, val in response.raw_headers if name.lower() == b"set-cookie"]
    assert set_cookies == ["cookie1=val1; Path=/", "cookie2=val2; Path=/"]


@pytest.mark.asyncio
async def test_lumen_proxy_sse_streaming_non_buffering():
    req = _make_dummy_request(
        path="/api/v1/chat/runs/run-123/events",
        headers={"X-Auth-Token": "token-1", "X-Project-Id": "proj-1"},
    )
    req.state.token_info = {"token": "token-1", "project_id": "proj-1"}

    chunk2_released = asyncio.Event()

    async def mock_aiter_bytes():
        yield b"data: chunk 1\n\n"
        await chunk2_released.wait()
        yield b"data: chunk 2\n\n"

    sent_requests: list[tuple[HttpxRequest, bool]] = []

    async def mock_send(outgoing_req: HttpxRequest, stream: bool = False):
        sent_requests.append((outgoing_req, stream))
        resp_headers = Headers([("content-type", "text/event-stream")])
        resp = MagicMock(spec=HttpxResponse)
        resp.status_code = 200
        resp.headers = resp_headers
        resp.aiter_bytes = mock_aiter_bytes
        resp.aclose = AsyncMock()
        return resp

    mock_client = MagicMock()
    mock_client.build_request.side_effect = lambda method, url, headers, content: HttpxRequest(
        method, url, headers=headers, content=content
    )
    mock_client.send = AsyncMock(side_effect=mock_send)
    mock_client.aclose = AsyncMock()

    with patch("app.services.service_proxy._get_internal_endpoint", return_value="http://lumen.internal"):
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await proxy("lumen", req, "/v1/runs/run-123/events")

    assert len(sent_requests) == 1
    _, stream = sent_requests[0]
    assert stream is True

    iterator = response.body_iterator
    chunk1 = await anext(iterator)
    assert chunk1 == b"data: chunk 1\n\n"

    assert not chunk2_released.is_set()

    chunk2_released.set()
    chunk2 = await anext(iterator)
    assert chunk2 == b"data: chunk 2\n\n"


@pytest.mark.asyncio
async def test_lumen_proxy_unavailable_catalog_503(api_client):
    app.dependency_overrides[get_token_info] = _authenticated
    with patch("app.services.service_proxy._get_internal_endpoint", return_value=None):
        response = await api_client.get("/api/v1/chat/conversations")

    assert response.status_code == 503
    assert response.json() == {"detail": "lumen 서비스를 사용할 수 없습니다"}


@pytest.mark.asyncio
async def test_external_v1_openai_anthropic_unmounted(api_client):
    resps = [
        await api_client.post("/v1/chat/completions", json={"model": "gpt-4"}),
        await api_client.post("/v1/messages", json={"model": "claude-3"}),
        await api_client.get("/v1/models"),
    ]
    for r in resps:
        assert r.status_code == 404
