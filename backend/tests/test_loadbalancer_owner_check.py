"""Loadbalancer (LB/listener/pool/member/HM) cross-project IDOR 거부 검증.

LB 의 owner check 가 통과하면 sub-resource (listener/pool/member/HM) 는 lb_id sub-path
이므로 간접적으로 보호된다 — _assert_lb_owner 한 군데 검증만으로 cross-project 차단.
"""

from unittest.mock import MagicMock, patch

import pytest


def _foreign_lb(project_id: str = "other-project-999"):
    m = MagicMock()
    m.project_id = project_id
    m.tenant_id = None
    return m


@pytest.mark.asyncio
async def test_get_lb_other_project_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.get("/api/loadbalancers/lb-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_lb_other_project_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.delete("/api/loadbalancers/lb-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_delete_other_project_lb(admin_client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    with patch("app.api.network.loadbalancers.octavia.delete_load_balancer", return_value=None):
        resp = await admin_client.delete("/api/loadbalancers/lb-foreign")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_listener_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.post(
        "/api/loadbalancers/lb-foreign/listeners",
        json={"protocol": "HTTP", "protocol_port": 80, "name": "l1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_listener_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.delete("/api/loadbalancers/lb-foreign/listeners/li-1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_pool_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.post(
        "/api/loadbalancers/lb-foreign/pools",
        json={"protocol": "HTTP", "lb_algorithm": "ROUND_ROBIN", "name": "p1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_member_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.post(
        "/api/loadbalancers/lb-foreign/pools/p-1/members",
        json={"address": "10.0.0.5", "protocol_port": 8080},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_health_monitor_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.post(
        "/api/loadbalancers/lb-foreign/pools/p-1/health-monitor",
        json={"type": "HTTP", "delay": 5, "timeout": 5, "max_retries": 3},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_member_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.delete("/api/loadbalancers/lb-foreign/pools/p-1/members/m-1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_pool_other_project_lb_returns_404(client, mock_conn):
    mock_conn.load_balancer.get_load_balancer = MagicMock(return_value=_foreign_lb())
    resp = await client.delete("/api/loadbalancers/lb-foreign/pools/p-1")
    assert resp.status_code == 404
