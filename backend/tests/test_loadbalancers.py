"""network/loadbalancers.py 엔드포인트 단위 테스트 (17개)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_list_lbs_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_lbs_success(client):
    with patch("app.api.network.loadbalancers.cached_call", new=AsyncMock(return_value=[])):
        resp = await client.get("/api/loadbalancers")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_lb_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/loadbalancers", json={"name": "lb1", "vip_subnet_id": "s1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_lb_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct, \
         patch("app.api.network.loadbalancers.invalidate", new=AsyncMock()):
        mock_oct.create_load_balancer.return_value = {"id": "lb-1", "name": "lb1"}
        resp = await client.post("/api/loadbalancers", json={"name": "lb1", "vip_subnet_id": "sub-1"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_lb_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers/lb-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_lb_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.get_load_balancer.return_value = {"id": "lb-1"}
        resp = await client.get("/api/loadbalancers/lb-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_lb_status_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers/lb-1/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_lb_status_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.get_lb_status_tree.return_value = {"id": "lb-1", "statuses": {}}
        resp = await client.get("/api/loadbalancers/lb-1/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_lb_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/loadbalancers/lb-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_lb_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct, \
         patch("app.api.network.loadbalancers.invalidate", new=AsyncMock()):
        mock_oct.delete_load_balancer.return_value = None
        resp = await client.delete("/api/loadbalancers/lb-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_listeners_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers/lb-1/listeners")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_listeners_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.list_listeners.return_value = []
        resp = await client.get("/api/loadbalancers/lb-1/listeners")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_listener_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/loadbalancers/lb-1/listeners", json={"protocol": "HTTP", "protocol_port": 80})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_listener_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.create_listener.return_value = {"id": "lis-1"}
        resp = await client.post("/api/loadbalancers/lb-1/listeners", json={"protocol": "HTTP", "protocol_port": 80})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_listener_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/loadbalancers/lb-1/listeners/lis-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_listener_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.delete_listener.return_value = None
        resp = await client.delete("/api/loadbalancers/lb-1/listeners/lis-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_pools_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers/lb-1/pools")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_pools_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.list_pools.return_value = []
        resp = await client.get("/api/loadbalancers/lb-1/pools")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_pool_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/loadbalancers/lb-1/pools", json={"protocol": "HTTP"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_pool_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.create_pool.return_value = {"id": "pool-1"}
        resp = await client.post("/api/loadbalancers/lb-1/pools", json={"protocol": "HTTP"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_pool_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/loadbalancers/lb-1/pools/pool-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_pool_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.delete_pool.return_value = None
        resp = await client.delete("/api/loadbalancers/lb-1/pools/pool-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_members_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers/lb-1/pools/pool-1/members")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_members_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.list_members.return_value = []
        resp = await client.get("/api/loadbalancers/lb-1/pools/pool-1/members")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_member_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/loadbalancers/lb-1/pools/pool-1/members",
                             json={"address": "10.0.0.1", "protocol_port": 80})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_member_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.add_member.return_value = {"id": "mem-1"}
        resp = await client.post("/api/loadbalancers/lb-1/pools/pool-1/members",
                                 json={"address": "10.0.0.1", "protocol_port": 80})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_remove_member_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/loadbalancers/lb-1/pools/pool-1/members/mem-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_remove_member_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.remove_member.return_value = None
        resp = await client.delete("/api/loadbalancers/lb-1/pools/pool-1/members/mem-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_health_monitors_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/loadbalancers/lb-1/pools/pool-1/health-monitor")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_health_monitors_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.list_health_monitors.return_value = []
        resp = await client.get("/api/loadbalancers/lb-1/pools/pool-1/health-monitor")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_health_monitor_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/loadbalancers/lb-1/pools/pool-1/health-monitor", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_health_monitor_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.create_health_monitor.return_value = {"id": "hm-1"}
        resp = await client.post("/api/loadbalancers/lb-1/pools/pool-1/health-monitor", json={})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_health_monitor_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/loadbalancers/lb-1/pools/pool-1/health-monitor/hm-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_health_monitor_success(client):
    with patch("app.api.network.loadbalancers.octavia") as mock_oct:
        mock_oct.delete_health_monitor.return_value = None
        resp = await client.delete("/api/loadbalancers/lb-1/pools/pool-1/health-monitor/hm-1")
    assert resp.status_code == 204
