"""VPN 에이전트 대면 API(register/desired-state/status) 베어러 토큰 인증 테스트.

에이전트 엔드포인트는 사용자 JWT가 아닌 베어러 토큰(vpn_agent_auth)으로 인증하며
fail-closed(무효/불일치 시 401/403)이다. `_verify_and_bind`가 DB 조회 이전에 실행되므로
인증 실패 케이스는 DB mock 없이도 검증 가능하다. 토큰 자체는 fakeredis(conftest 전역
fixture)에 실제로 저장/조회되므로 real end-to-end 토큰 발급 흐름으로 테스트한다.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import vpn_agent_auth, vpn_config


def _server_record(**overrides) -> dict:
    base = {
        "id": "server-1",
        "project_id": "test-project-123",
        "name": "vpn-gw-1",
        "status": "PROVISIONING",
        "status_reason": "에이전트 register 대기 중",
        "server_public_key": None,
        "endpoint_ip": "203.0.113.10",
        "listen_port": 51820,
        "tunnel_cidr": "10.8.0.0/24",
    }
    base.update(overrides)
    return base


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 인증 실패 (401/403) — 3개 엔드포인트 공통
# ---------------------------------------------------------------------------

_AGENT_ENDPOINTS = [
    ("post", "/api/v1/vpn/servers/server-1/agent/register", {"public_key": "A" * 43 + "="}),
    ("get", "/api/v1/vpn/servers/server-1/agent/desired-state", None),
    ("post", "/api/v1/vpn/servers/server-1/agent/status", {"peers": []}),
]


class TestAgentAuthMissingToken:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _AGENT_ENDPOINTS)
    async def test_no_bearer_token_returns_401(self, api_client, method, path, body):
        call = getattr(api_client, method)
        resp = await (call(path, json=body) if body is not None else call(path))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _AGENT_ENDPOINTS)
    async def test_non_bearer_auth_scheme_returns_401(self, api_client, method, path, body):
        headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        call = getattr(api_client, method)
        resp = await (call(path, json=body, headers=headers) if body is not None else call(path, headers=headers))
        assert resp.status_code == 401


class TestAgentAuthInvalidToken:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _AGENT_ENDPOINTS)
    async def test_invalid_token_returns_401(self, api_client, method, path, body):
        headers = {"Authorization": "Bearer totally-invalid-token-that-was-never-issued"}
        call = getattr(api_client, method)
        resp = await (call(path, json=body, headers=headers) if body is not None else call(path, headers=headers))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_token_returns_401(self, api_client):
        """토큰 발급 후 폐기(revoke)되면 이후 요청은 401이어야 한다."""
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        await vpn_agent_auth.revoke_report_token_by_server("server-1")
        resp = await api_client.get(
            "/api/v1/vpn/servers/server-1/agent/desired-state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


class TestAgentAuthServerIdMismatch:
    @pytest.mark.asyncio
    async def test_token_bound_to_different_server_returns_403(self, api_client):
        """server-A 용 토큰으로 server-B 경로를 호출하면 403(귀속 불일치)."""
        token = await vpn_agent_auth.issue_report_token("server-A", "test-project-123")
        resp = await api_client.get(
            "/api/v1/vpn/servers/server-B/agent/desired-state",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_register_with_mismatched_server_id_returns_403(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-A", "test-project-123")
        resp = await api_client.post(
            "/api/v1/vpn/servers/server-B/agent/register",
            json={"public_key": "A" * 43 + "="},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_status_with_mismatched_server_id_returns_403(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-A", "test-project-123")
        resp = await api_client.post(
            "/api/v1/vpn/servers/server-B/agent/status",
            json={"peers": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 정상 흐름 (대조군 — false positive 방지)
# ---------------------------------------------------------------------------


class TestAgentRegisterHappyPath:
    @pytest.mark.asyncio
    async def test_valid_token_register_updates_public_key_and_status(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        with patch("app.api.vpn.agent.vpn_db") as mock_db:
            mock_db.get_server_by_id = AsyncMock(return_value=_server_record(status="CREATING"))
            mock_db.update_server_status = AsyncMock()
            resp = await api_client.post(
                "/api/v1/vpn/servers/server-1/agent/register",
                json={"public_key": "A" * 43 + "="},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 204
        mock_db.update_server_status.assert_called_once()
        call_args = mock_db.update_server_status.call_args
        assert call_args.args[0] == "server-1"
        assert call_args.args[1] == "ACTIVE"
        assert call_args.kwargs["server_public_key"] == "A" * 43 + "="

    @pytest.mark.asyncio
    async def test_register_404_when_server_not_found(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        with patch("app.api.vpn.agent.vpn_db") as mock_db:
            mock_db.get_server_by_id = AsyncMock(return_value=None)
            resp = await api_client.post(
                "/api/v1/vpn/servers/server-1/agent/register",
                json={"public_key": "A" * 43 + "="},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_register_rejects_invalid_public_key_format(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        resp = await api_client.post(
            "/api/v1/vpn/servers/server-1/agent/register",
            json={"public_key": "not-a-valid-wg-key"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


class TestAgentDesiredStateHappyPath:
    @pytest.mark.asyncio
    async def test_valid_token_returns_desired_state(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        with patch("app.api.vpn.agent.vpn_db") as mock_db:
            mock_db.get_server_by_id = AsyncMock(
                return_value=_server_record(status="ACTIVE", server_public_key="A" * 43 + "=")
            )
            mock_db.list_all_active_clients = AsyncMock(return_value=[])
            resp = await api_client.get(
                "/api/v1/vpn/servers/server-1/agent/desired-state",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["listen_port"] == 51820
        assert body["tunnel_cidr"] == "10.8.0.0/24"
        assert body["peers"] == []

    @pytest.mark.asyncio
    async def test_desired_state_404_when_server_not_found(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        with patch("app.api.vpn.agent.vpn_db") as mock_db:
            mock_db.get_server_by_id = AsyncMock(return_value=None)
            resp = await api_client.get(
                "/api/v1/vpn/servers/server-1/agent/desired-state",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_desired_state_excludes_disabled_clients(self, api_client):
        """enabled=False 클라이언트는 peers 목록에서 제외되어야 한다 (soft-disable)."""
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        clients = [
            {
                "id": "c1",
                "public_key": "enabled-client-pub-AAAAAAAAAAAAAAAAAAAAAAAAA=",
                "preshared_key_encrypted": None,
                "tunnel_ip": "10.8.0.2",
                "enabled": True,
            },
            {
                "id": "c2",
                "public_key": "disabled-client-pub-AAAAAAAAAAAAAAAAAAAAAAAA=",
                "preshared_key_encrypted": None,
                "tunnel_ip": "10.8.0.3",
                "enabled": False,
            },
        ]
        with patch("app.api.vpn.agent.vpn_db") as mock_db:
            mock_db.get_server_by_id = AsyncMock(
                return_value=_server_record(status="ACTIVE", server_public_key="A" * 43 + "=")
            )
            mock_db.list_all_active_clients = AsyncMock(return_value=clients)
            resp = await api_client.get(
                "/api/v1/vpn/servers/server-1/agent/desired-state",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["peers"]) == 1
        assert body["peers"][0]["public_key"] == "enabled-client-pub-AAAAAAAAAAAAAAAAAAAAAAAAA="
        assert body["peers"][0]["allowed_ips"] == ["10.8.0.2/32"]


class TestAgentStatusHappyPath:
    @pytest.mark.asyncio
    async def test_valid_token_stores_status_report(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        resp = await api_client.post(
            "/api/v1/vpn/servers/server-1/agent/status",
            json={
                "peers": [
                    {
                        "public_key": "A" * 43 + "=",
                        "last_handshake_at": "2026-07-12T00:00:00+00:00",
                        "rx_bytes": 100,
                        "tx_bytes": 200,
                    }
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        stored = await vpn_agent_auth.get_status_result("server-1")
        assert stored is not None
        assert stored["peers"][0]["rx_bytes"] == 100

    @pytest.mark.asyncio
    async def test_status_report_rejects_invalid_public_key(self, api_client):
        token = await vpn_agent_auth.issue_report_token("server-1", "test-project-123")
        resp = await api_client.post(
            "/api/v1/vpn/servers/server-1/agent/status",
            json={"peers": [{"public_key": "not-valid"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# desired-state 렌더 로직 (순수 함수 — vpn_config.render_agent_desired_state)
# ---------------------------------------------------------------------------


class TestRenderAgentDesiredState:
    def test_excludes_disabled_clients(self):
        clients = [
            {"public_key": "pub-a", "tunnel_ip": "10.8.0.2", "enabled": True},
            {"public_key": "pub-b", "tunnel_ip": "10.8.0.3", "enabled": False},
        ]
        result = vpn_config.render_agent_desired_state(listen_port=51820, tunnel_cidr="10.8.0.0/24", clients=clients)
        pubkeys = [p["public_key"] for p in result["peers"]]
        assert "pub-a" in pubkeys
        assert "pub-b" not in pubkeys

    def test_includes_all_enabled_clients(self):
        clients = [
            {"public_key": "pub-a", "tunnel_ip": "10.8.0.2", "enabled": True},
            {"public_key": "pub-b", "tunnel_ip": "10.8.0.3", "enabled": True},
        ]
        result = vpn_config.render_agent_desired_state(listen_port=51820, tunnel_cidr="10.8.0.0/24", clients=clients)
        assert len(result["peers"]) == 2

    def test_default_enabled_true_when_key_missing(self):
        """enabled 키가 없으면 기본값 True로 처리되어야 한다."""
        clients = [{"public_key": "pub-a", "tunnel_ip": "10.8.0.2"}]
        result = vpn_config.render_agent_desired_state(listen_port=51820, tunnel_cidr="10.8.0.0/24", clients=clients)
        assert len(result["peers"]) == 1

    def test_peer_allowed_ips_is_tunnel_ip_slash_32(self):
        clients = [{"public_key": "pub-a", "tunnel_ip": "10.8.0.5", "enabled": True}]
        result = vpn_config.render_agent_desired_state(listen_port=51820, tunnel_cidr="10.8.0.0/24", clients=clients)
        assert result["peers"][0]["allowed_ips"] == ["10.8.0.5/32"]

    def test_empty_clients_returns_empty_peers(self):
        result = vpn_config.render_agent_desired_state(listen_port=51820, tunnel_cidr="10.8.0.0/24", clients=[])
        assert result["peers"] == []
        assert result["listen_port"] == 51820
        assert result["tunnel_cidr"] == "10.8.0.0/24"
