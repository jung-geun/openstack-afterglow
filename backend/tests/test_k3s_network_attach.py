"""k3s 노드 네트워크 attach/detach API 단위 테스트.

FastAPI Depends() 는 라우트 정의 시점에 함수 참조를 캡처하므로 모듈 이름 patch 가
재라우팅되지 않는다. 따라서 `app.dependency_overrides` 로 인증/conn 의존성을 교체하고,
핸들러 내부에서 import 되는 nova/k3s_cluster/invalidate/rec 만 patch 한다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_os_conn, get_token_info
from app.main import app


@pytest.fixture
def mock_cluster():
    return {
        "id": "cluster-1",
        "name": "test-cluster",
        "server_vm_id": "server-vm-1",
        "agent_vm_ids": ["agent-vm-1", "agent-vm-2"],
        "deleted_at": None,
    }


@pytest.fixture
def mock_conn():
    """k3s 핸들러가 사용하는 conn._afterglow_project_id 만 stub."""
    conn = MagicMock()
    conn._afterglow_project_id = "proj-1"
    conn._afterglow_token = "test-token"
    conn._afterglow_user_id = "test-user-1"
    conn.close = MagicMock()
    return conn


@pytest.fixture
async def client(mock_conn):
    async def override_get_os_conn():
        try:
            yield mock_conn
        finally:
            pass

    async def override_get_token_info():
        return {
            "token": "test-token",
            "project_id": "proj-1",
            "project_name": "test-project",
            "user_id": "test-user-1",
            "username": "testuser",
            "roles": ["member"],
            "expires_at": "2099-01-01T00:00:00Z",
            "is_system_admin": False,
        }

    app.dependency_overrides[get_os_conn] = override_get_os_conn
    app.dependency_overrides[get_token_info] = override_get_token_info
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Auth-Token": "test-token", "X-Project-Id": "proj-1"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_attach_interface_wrong_vm_403(client, mock_cluster):
    """클러스터에 속하지 않은 vm_id로 attach 시 403."""
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_k3s_cluster:
        mock_k3s_cluster.get_cluster = AsyncMock(return_value=mock_cluster)
        resp = await client.post(
            "/api/k3s/clusters/cluster-1/nodes/unknown-vm/interfaces",
            json={"net_id": "net-1"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_attach_interface_cluster_not_found_404(client):
    """존재하지 않는 cluster_id로 attach 시 404."""
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_k3s_cluster:
        mock_k3s_cluster.get_cluster = AsyncMock(return_value=None)
        resp = await client.post(
            "/api/k3s/clusters/nonexistent/nodes/server-vm-1/interfaces",
            json={"net_id": "net-1"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_attach_server_vm_success(client, mock_cluster):
    """서버 VM에 인터페이스 attach 성공."""
    with (
        patch("app.api.k3s.clusters.k3s_cluster") as mock_k3s_cluster,
        patch("app.api.k3s.clusters.nova") as mock_nova,
        patch("app.api.k3s.clusters.invalidate", new_callable=AsyncMock),
        patch("app.api.k3s.clusters.rec", new_callable=AsyncMock),
    ):
        mock_k3s_cluster.get_cluster = AsyncMock(return_value=mock_cluster)
        mock_nova.attach_interface.return_value = {
            "port_id": "port-99",
            "net_id": "net-1",
            "fixed_ips": [{"ip_address": "192.168.100.5", "subnet_id": "sub-1"}],
        }
        resp = await client.post(
            "/api/k3s/clusters/cluster-1/nodes/server-vm-1/interfaces",
            json={"net_id": "net-1"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["port_id"] == "port-99"
    assert data["node_role"] == "server"


@pytest.mark.asyncio
async def test_detach_agent_vm_success(client, mock_cluster):
    """에이전트 VM에서 인터페이스 detach 성공."""
    with (
        patch("app.api.k3s.clusters.k3s_cluster") as mock_k3s_cluster,
        patch("app.api.k3s.clusters.nova") as mock_nova,
        patch("app.api.k3s.clusters.invalidate", new_callable=AsyncMock),
        patch("app.api.k3s.clusters.rec", new_callable=AsyncMock),
    ):
        mock_k3s_cluster.get_cluster = AsyncMock(return_value=mock_cluster)
        mock_nova.detach_interface.return_value = None
        resp = await client.delete(
            "/api/k3s/clusters/cluster-1/nodes/agent-vm-1/interfaces/port-old",
        )
    assert resp.status_code == 204
