"""Network/Router/SG/FIP/Subnet 의 cross-project IDOR 거부 검증 (defense-in-depth).

OpenStack RBAC 가 1차 방어선이지만, policy 가 광범위하거나 admin 토큰 누설 시
백엔드에서 한번 더 차단하는 `assert_resource_owner` 동작을 회귀 테스트한다.
"""

from unittest.mock import MagicMock, patch

import pytest


def _foreign_resource(project_id: str = "other-project-999"):
    m = MagicMock()
    m.project_id = project_id
    m.tenant_id = None
    m.is_router_external = False
    m.is_shared = False
    return m


# ────── Network ──────


@pytest.mark.asyncio
async def test_get_network_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_network = MagicMock(return_value=_foreign_resource())
    resp = await client.get("/api/networks/net-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_external_network_passes_owner_check(client, mock_conn):
    """외부/공유 네트워크는 owner check 면제 — cross-project 노출이 정상."""
    ext = MagicMock()
    ext.project_id = "other-project-999"
    ext.is_router_external = True
    ext.is_shared = False
    mock_conn.network.get_network = MagicMock(return_value=ext)
    with patch(
        "app.api.network.networks.neutron.get_network_detail",
        return_value={
            "id": "net-ext",
            "name": "ext",
            "status": "ACTIVE",
            "subnets": [],
            "is_external": True,
            "is_shared": False,
            "subnet_details": [],
            "routers": [],
        },
    ):
        resp = await client.get("/api/networks/net-ext")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_network_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_network = MagicMock(return_value=_foreign_resource())
    resp = await client.delete("/api/networks/net-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_delete_other_project_network(admin_client, mock_conn):
    mock_conn.network.get_network = MagicMock(return_value=_foreign_resource())
    with patch("app.api.network.networks.neutron.delete_network", return_value=None):
        resp = await admin_client.delete("/api/networks/net-foreign")
    assert resp.status_code == 204


# ────── Subnet ──────


@pytest.mark.asyncio
async def test_update_subnet_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_subnet = MagicMock(return_value=_foreign_resource())
    resp = await client.put(
        "/api/networks/subnets/sub-foreign",
        json={"name": "x", "gateway_ip": None, "enable_dhcp": True},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_subnet_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_subnet = MagicMock(return_value=_foreign_resource())
    resp = await client.delete("/api/networks/subnets/sub-foreign")
    assert resp.status_code == 404


# ────── Floating IP ──────


@pytest.mark.asyncio
async def test_associate_fip_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_ip = MagicMock(return_value=_foreign_resource())
    resp = await client.post("/api/networks/floating-ips/fip-foreign/associate", json={"instance_id": "i-1"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_disassociate_fip_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_ip = MagicMock(return_value=_foreign_resource())
    resp = await client.post("/api/networks/floating-ips/fip-foreign/disassociate")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_fip_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_ip = MagicMock(return_value=_foreign_resource())
    resp = await client.delete("/api/networks/floating-ips/fip-foreign")
    assert resp.status_code == 404


# ────── Router ──────


@pytest.mark.asyncio
async def test_get_router_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_router = MagicMock(return_value=_foreign_resource())
    resp = await client.get("/api/routers/r-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_router_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_router = MagicMock(return_value=_foreign_resource())
    resp = await client.delete("/api/routers/r-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_interface_other_project_router_returns_404(client, mock_conn):
    mock_conn.network.get_router = MagicMock(return_value=_foreign_resource())
    resp = await client.post("/api/routers/r-foreign/interfaces", json={"subnet_id": "s-1"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_gateway_other_project_router_returns_404(client, mock_conn):
    mock_conn.network.get_router = MagicMock(return_value=_foreign_resource())
    resp = await client.post("/api/routers/r-foreign/gateway", json={"external_network_id": "ext-1"})
    assert resp.status_code == 404


# ────── Security Group ──────


@pytest.mark.asyncio
async def test_delete_sg_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_security_group = MagicMock(return_value=_foreign_resource())
    resp = await client.delete("/api/security-groups/sg-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_sg_rule_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_security_group = MagicMock(return_value=_foreign_resource())
    resp = await client.post(
        "/api/security-groups/sg-foreign/rules",
        json={"direction": "ingress", "protocol": "tcp"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_sg_rule_other_project_returns_404(client, mock_conn):
    mock_conn.network.get_security_group = MagicMock(return_value=_foreign_resource())
    resp = await client.delete("/api/security-groups/sg-foreign/rules/rule-1")
    assert resp.status_code == 404
