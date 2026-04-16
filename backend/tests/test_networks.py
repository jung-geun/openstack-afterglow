"""네트워크 및 Floating IP API 테스트."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.storage import FloatingIpInfo


def make_fip(project_id: str = "test-project-123") -> FloatingIpInfo:
    return FloatingIpInfo(
        id="fip-1", floating_ip_address="1.2.3.4",
        fixed_ip_address=None, status="DOWN",
        port_id=None, floating_network_id="net-ext",
        project_id=project_id,
    )


def _make_network():
    return {
        "id": "net-1", "name": "mynet", "status": "ACTIVE",
        "project_id": "test-project-123", "shared": False,
        "admin_state_up": True, "subnets": [],
    }


@pytest.mark.asyncio
async def test_list_networks_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/networks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_networks_success(client):
    with patch("app.api.network.networks.cached_call", new=AsyncMock(return_value=[])):
        resp = await client.get("/api/networks")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_network_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/networks", json={"name": "net1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_network_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/networks/net-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_network_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/networks/net-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_network_success(client):
    with patch("app.api.network.networks.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/networks/net-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_subnet_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/networks/net-1/subnets",
                             json={"name": "sub1", "cidr": "10.0.0.0/24", "ip_version": 4})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_subnet_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/networks/subnets/sub-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_topology_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/networks/topology")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_floating_ips_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/networks/floating-ips")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_floating_ips_filters_by_project(client, mock_conn):
    """Floating IP 목록이 현재 프로젝트로 필터링됨을 확인 (Task 2 버그 수정)."""
    captured_project_id = None

    def mock_list_fips(conn, project_id=None):
        nonlocal captured_project_id
        captured_project_id = project_id
        return [make_fip(project_id or "")]

    with patch("app.api.network.networks.neutron.list_floating_ips", side_effect=mock_list_fips):
        resp = await client.get("/api/networks/floating-ips")

    assert resp.status_code == 200
    # project_id가 전달되었어야 함
    assert captured_project_id == "test-project-123"


@pytest.mark.asyncio
async def test_create_floating_ip_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/networks/floating-ips", json={"floating_network_id": "ext-net"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_associate_floating_ip_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/networks/floating-ips/fip-1/associate",
                             json={"port_id": "port-1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_disassociate_floating_ip_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/networks/floating-ips/fip-1/disassociate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_floating_ip_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/networks/floating-ips/fip-1")
    assert resp.status_code == 401
