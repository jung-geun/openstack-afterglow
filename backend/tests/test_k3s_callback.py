"""K3s callback 엔드포인트 테스트 (/api/k3s/callback)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_callback_invalid_token_returns_403():
    """무효 토큰으로 콜백 요청 시 403을 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.k3s.callback.k3s_cluster") as mock_db:
            mock_db.consume_callback_token = AsyncMock(return_value=None)
            resp = await ac.post(
                "/api/k3s/callback",
                json={
                    "token": "invalid-token",
                    "success": True,
                    "kubeconfig": "apiVersion: v1\n",
                    "node_token": "secret",
                    "server_ip": "10.0.0.1",
                },
            )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_callback_failure_updates_status():
    """success=false 콜백 시 클러스터 상태를 ERROR로 업데이트해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.k3s.callback.k3s_cluster") as mock_db:
            mock_db.consume_callback_token = AsyncMock(return_value={"project_id": "proj-1", "cluster_id": "cluster-1"})
            mock_db.update_cluster_status = AsyncMock()
            resp = await ac.post(
                "/api/k3s/callback",
                json={
                    "token": "valid-token",
                    "success": False,
                    "error": "k3s 설치 실패",
                },
            )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_db.update_cluster_status.assert_called_once_with(
        "proj-1", "cluster-1", "ERROR", "서버 초기화 실패: k3s 설치 실패"
    )


@pytest.mark.asyncio
async def test_callback_missing_kubeconfig_updates_error():
    """success=true이지만 kubeconfig 누락 시 ERROR로 처리해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.k3s.callback.k3s_cluster") as mock_db:
            mock_db.consume_callback_token = AsyncMock(return_value={"project_id": "proj-1", "cluster_id": "cluster-1"})
            mock_db.update_cluster_status = AsyncMock()
            resp = await ac.post(
                "/api/k3s/callback",
                json={
                    "token": "valid-token",
                    "success": True,
                    # kubeconfig, node_token, server_ip 모두 누락
                },
            )
    assert resp.status_code == 200
    mock_db.update_cluster_status.assert_called_once()
    call_args = mock_db.update_cluster_status.call_args
    assert call_args.args[2] == "ERROR"


@pytest.mark.asyncio
async def test_callback_missing_node_token_updates_error():
    """node_token 누락 시 ERROR로 처리해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.k3s.callback.k3s_cluster") as mock_db:
            mock_db.consume_callback_token = AsyncMock(return_value={"project_id": "proj-1", "cluster_id": "cluster-1"})
            mock_db.update_cluster_status = AsyncMock()
            resp = await ac.post(
                "/api/k3s/callback",
                json={
                    "token": "valid-token",
                    "success": True,
                    "kubeconfig": "apiVersion: v1\n",
                    # node_token 누락
                    "server_ip": "10.0.0.1",
                },
            )
    assert resp.status_code == 200
    mock_db.update_cluster_status.assert_called_once()
    call_args = mock_db.update_cluster_status.call_args
    assert call_args.args[2] == "ERROR"


@pytest.mark.asyncio
async def test_callback_success_triggers_agent_provisioning():
    """유효 콜백 성공 시 에이전트 VM 생성 태스크를 시작해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.k3s.callback.k3s_cluster") as mock_db:
            mock_db.consume_callback_token = AsyncMock(return_value={"project_id": "proj-1", "cluster_id": "cluster-1"})
            mock_db.update_cluster_status = AsyncMock()
            mock_db.store_kubeconfig = AsyncMock()
            with patch("app.api.k3s.callback.asyncio") as mock_asyncio:
                mock_asyncio.create_task = AsyncMock()
                resp = await ac.post(
                    "/api/k3s/callback",
                    json={
                        "token": "valid-token",
                        "success": True,
                        "kubeconfig": "apiVersion: v1\nkind: Config\n",
                        "node_token": "K10secret::server:abc123",
                        "server_ip": "10.0.0.1",
                    },
                )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    mock_db.store_kubeconfig.assert_called_once_with("proj-1", "cluster-1", "apiVersion: v1\nkind: Config\n")
    mock_db.update_cluster_status.assert_called_once_with(
        "proj-1", "cluster-1", "PROVISIONING",
        server_ip="10.0.0.1",
        api_address="https://10.0.0.1:6443",
        node_token="K10secret::server:abc123",
    )
    mock_asyncio.create_task.assert_called_once()


@pytest.mark.asyncio
async def test_callback_token_consumed_only_once():
    """일회성 토큰: 첫 번째 요청 후 같은 토큰으로 재시도 시 403이어야 한다."""
    call_count = 0

    async def side_effect(token):
        nonlocal call_count
        call_count += 1
        # 첫 호출에만 유효 데이터 반환, 이후는 None
        if call_count == 1:
            return {"project_id": "proj-1", "cluster_id": "cluster-1"}
        return None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.api.k3s.callback.k3s_cluster") as mock_db:
            mock_db.consume_callback_token = AsyncMock(side_effect=side_effect)
            mock_db.update_cluster_status = AsyncMock()
            mock_db.store_kubeconfig = AsyncMock()
            with patch("app.api.k3s.callback.asyncio"):
                # 첫 번째 성공 요청 (success=false라서 update만)
                resp1 = await ac.post(
                    "/api/k3s/callback",
                    json={"token": "one-time-token", "success": False, "error": "fail"},
                )
                assert resp1.status_code == 200

            # 두 번째 동일 토큰 → 403
            resp2 = await ac.post(
                "/api/k3s/callback",
                json={"token": "one-time-token", "success": False},
            )
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_callback_requires_post():
    """GET /api/k3s/callback은 405를 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/callback")
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_callback_invalid_json_returns_422():
    """유효하지 않은 JSON body는 422를 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/k3s/callback",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 422
