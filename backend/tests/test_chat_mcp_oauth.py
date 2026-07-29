"""Remote MCP OAuth discovery and chat-extension routing contracts."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.api.chat import extensions
from app.api.chat import mcp_oauth as mcp_oauth_callback
from app.services.chat import mcp_oauth


class TestMcpOAuthCallbackUrl:
    def test_uses_frontend_origin_when_public_api_base_is_unset(self, monkeypatch):
        monkeypatch.setattr(
            mcp_oauth,
            "get_settings",
            lambda: SimpleNamespace(public_api_base="", frontend_base_url="https://console.example"),
        )

        assert mcp_oauth._callback_url() == "https://console.example/api/v1/chat/mcp-oauth/callback"

    def test_uses_explicit_configured_callback_url(self, monkeypatch):
        callback_url = "https://oauth.example.test/custom/mcp-callback"
        monkeypatch.setattr(
            mcp_oauth,
            "get_settings",
            lambda: SimpleNamespace(
                chat_mcp_oauth_callback_url=callback_url,
                public_api_base="https://api.example.test",
                frontend_base_url="https://console.example.test",
            ),
        )

        assert mcp_oauth._callback_url() == callback_url

    def test_rejects_victim_browser_nonce_for_attacker_request(self):
        attacker_nonce = "a" * 43
        with pytest.raises(mcp_oauth.McpOAuthError, match="not initiated by this browser"):
            mcp_oauth._verify_initiator_nonce(
                {"initiator_nonce_hash": mcp_oauth._hash(attacker_nonce)},
                "victim-browser-nonce",
            )


class TestMcpOAuthDiscovery:
    async def test_discovers_https_metadata_and_registration_endpoint(self, monkeypatch):
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            payloads = {
                "https://mcp.example/.well-known/oauth-protected-resource": {
                    "resource": "https://mcp.example/mcp",
                    "authorization_servers": ["https://auth.example"],
                },
                "https://auth.example/.well-known/oauth-authorization-server": {
                    "authorization_endpoint": "https://auth.example/authorize",
                    "token_endpoint": "https://auth.example/token",
                    "registration_endpoint": "https://auth.example/register",
                },
            }
            return httpx.Response(200, json=payloads[str(request.url)])

        monkeypatch.setattr(
            mcp_oauth,
            "_http_client",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://unused.example"),
        )

        metadata = await mcp_oauth._discover("https://mcp.example/mcp")

        assert metadata == {
            "authorization_endpoint": "https://auth.example/authorize",
            "token_endpoint": "https://auth.example/token",
            "registration_endpoint": "https://auth.example/register",
            "resource": "https://mcp.example/mcp",
        }
        assert seen == [
            "https://mcp.example/.well-known/oauth-protected-resource",
            "https://auth.example/.well-known/oauth-authorization-server",
        ]

    async def test_rejects_metadata_without_dynamic_registration(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "mcp.example":
                return httpx.Response(200, json={"authorization_servers": ["https://auth.example"]})
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://auth.example/authorize",
                    "token_endpoint": "https://auth.example/token",
                },
            )

        monkeypatch.setattr(
            mcp_oauth,
            "_http_client",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://unused.example"),
        )

        with pytest.raises(mcp_oauth.McpOAuthError, match="registration endpoint"):
            await mcp_oauth._discover("https://mcp.example/mcp")


class TestMcpOAuthRoutes:
    async def test_owner_can_start_oauth(self, client, monkeypatch):
        async def fake_begin(server_id, *, user_id, project_id, initiator_nonce):
            assert (server_id, user_id, project_id) == (7, "test-user-123", "test-project-123")
            assert len(initiator_nonce) >= 32
            return {"authorization_url": "https://auth.example/authorize?state=opaque"}

        monkeypatch.setattr(extensions.mcp_oauth, "begin", fake_begin)

        response = await client.post("/api/v1/chat/mcp-servers/7/oauth/start")

        assert response.status_code == 200
        assert response.json() == {"authorization_url": "https://auth.example/authorize?state=opaque"}
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=lax" in response.headers["set-cookie"].lower()
        assert "secure" in response.headers["set-cookie"].lower()

    async def test_callback_passes_only_the_initiating_browser_cookie(self, client, monkeypatch):
        received: list[str | None] = []

        async def fake_complete(*, state, code, error, initiator_nonce):
            assert (state, code, error) == ("opaque-state", "oauth-code", None)
            received.append(initiator_nonce)
            return 7

        monkeypatch.setattr(mcp_oauth_callback.mcp_oauth, "complete", fake_complete)
        client.cookies.set(mcp_oauth.INITIATOR_COOKIE, "initiator-browser-nonce")

        response = await client.get(
            "/api/v1/chat/mcp-oauth/callback?state=opaque-state&code=oauth-code",
            follow_redirects=False,
        )

        assert response.status_code in {200, 303}
        assert received == ["initiator-browser-nonce"]
        assert "max-age=0" in response.headers["set-cookie"].lower()

    async def test_owner_can_read_and_disconnect_oauth(self, client, monkeypatch):
        async def fake_status(server_id, *, user_id, project_id):
            assert (server_id, user_id, project_id) == (7, "test-user-123", "test-project-123")
            return {"mcp_server_id": 7, "required": True, "connected": True, "expires_at": None}

        disconnected: list[tuple[int, str, str]] = []

        async def fake_disconnect(server_id, *, user_id, project_id):
            disconnected.append((server_id, user_id, project_id))

        monkeypatch.setattr(extensions.mcp_oauth, "status", fake_status)
        monkeypatch.setattr(extensions.mcp_oauth, "disconnect", fake_disconnect)

        status = await client.get("/api/v1/chat/mcp-servers/7/oauth")
        deleted = await client.delete("/api/v1/chat/mcp-servers/7/oauth")

        assert status.status_code == 200
        assert status.json()["connected"] is True
        assert deleted.status_code == 204
        assert disconnected == [(7, "test-user-123", "test-project-123")]
