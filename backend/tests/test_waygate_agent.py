"""Permanent Afterglow proxy contract for baked Waygate agent URLs."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,upstream_path,body",
    [
        (
            "post",
            "/api/v1/waygate/servers/server-1/agent/register",
            "/v1/servers/server-1/agent/register",
            {"public_key": "A" * 43 + "="},
        ),
        (
            "get",
            "/api/v1/waygate/servers/server-1/agent/desired-state",
            "/v1/servers/server-1/agent/desired-state",
            None,
        ),
        (
            "post",
            "/api/v1/waygate/servers/server-1/agent/status",
            "/v1/servers/server-1/agent/status",
            {"peers": []},
        ),
    ],
)
async def test_baked_agent_route_proxies_to_waygate(api_client, method, path, upstream_path, body):
    forwarded = JSONResponse(status_code=207, content={"forwarded": True})
    with patch("app.api.waygate.agent.proxy_passthrough", new=AsyncMock(return_value=forwarded)) as proxy_call:
        call = getattr(api_client, method)
        response = await (call(path, json=body) if body is not None else call(path))

    assert response.status_code == 207
    assert response.json() == {"forwarded": True}
    args = proxy_call.await_args.args
    assert args[0] == "waygate"
    assert args[2] == upstream_path


@pytest.mark.asyncio
async def test_baked_agent_route_does_not_require_browser_auth(api_client):
    forwarded = JSONResponse(status_code=401, content={"detail": "invalid machine token"})
    with patch("app.api.waygate.agent.proxy_passthrough", new=AsyncMock(return_value=forwarded)) as proxy_call:
        response = await api_client.get(
            "/api/v1/waygate/servers/server-1/agent/desired-state",
            headers={"Authorization": "Bearer machine-token"},
        )

    assert response.status_code == 401
    request = proxy_call.await_args.args[1]
    assert request.headers["authorization"] == "Bearer machine-token"
