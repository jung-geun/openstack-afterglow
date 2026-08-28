"""Afterglow browser proxy contract for the extracted Waygate service."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_token_info
from app.main import app


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,upstream_path,body",
    [
        ("get", "/api/v1/waygate/servers", "/v1/servers", None),
        ("post", "/api/v1/waygate/servers", "/v1/servers", {"name": "gateway"}),
        (
            "patch",
            "/api/v1/waygate/servers/server-1/clients/client-1",
            "/v1/servers/server-1/clients/client-1",
            {"enabled": False},
        ),
        ("delete", "/api/v1/waygate/servers/server-1", "/v1/servers/server-1", None),
    ],
)
async def test_browser_routes_proxy_to_catalog_service(api_client, method, path, upstream_path, body):
    app.dependency_overrides[get_token_info] = _authenticated
    forwarded = JSONResponse(status_code=207, content={"forwarded": True})
    with patch("app.api.waygate.proxy.proxy", new=AsyncMock(return_value=forwarded)) as proxy_call:
        call = getattr(api_client, method)
        response = await (call(path, json=body) if body is not None else call(path))

    assert response.status_code == 207
    assert response.json() == {"forwarded": True}
    service_type, request, upstream = proxy_call.await_args.args
    assert service_type == "waygate"
    assert upstream == upstream_path
    assert request.state.token_info["token"] == "caller-token"


@pytest.mark.asyncio
async def test_browser_proxy_requires_authentication(api_client):
    with patch("app.api.waygate.proxy.proxy", new=AsyncMock()) as proxy_call:
        response = await api_client.get("/api/v1/waygate/servers")

    assert response.status_code == 401
    proxy_call.assert_not_awaited()
