"""storage/share_networks.py 엔드포인트 단위 테스트 (4개, manila 필요)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_share_networks_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/share-networks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_share_networks_success(client):
    with patch("app.api.storage.share_networks.cached_call", new=AsyncMock(return_value=[])):
        resp = await client.get("/api/share-networks")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_share_network_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/share-networks/sn-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_share_network_success(client):
    sn = {
        "id": "sn-1",
        "name": "net1",
        "status": "active",
        "neutron_net_id": "n1",
        "neutron_subnet_id": "sub1",
        "description": "",
        "created_at": None,
    }
    with patch("app.api.storage.share_networks.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=sn)
        resp = await client.get("/api/share-networks/sn-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_share_network_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/share-networks", json={"name": "sn1", "neutron_net_id": "n1", "neutron_subnet_id": "sub1"}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_share_network_success(client):
    sn = {
        "id": "sn-1",
        "name": "sn1",
        "status": "active",
        "neutron_net_id": "n1",
        "neutron_subnet_id": "sub1",
        "description": "",
        "created_at": None,
    }
    with (
        patch("app.api.storage.share_networks.asyncio") as mock_asyncio,
        patch("app.api.storage.share_networks.invalidate", new=AsyncMock()),
    ):
        mock_asyncio.to_thread = AsyncMock(return_value=sn)
        resp = await client.post(
            "/api/share-networks", json={"name": "sn1", "neutron_net_id": "n1", "neutron_subnet_id": "sub1"}
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_share_network_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/share-networks/sn-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_share_network_success(client):
    with (
        patch("app.api.storage.share_networks.asyncio") as mock_asyncio,
        patch("app.api.storage.share_networks.invalidate", new=AsyncMock()),
    ):
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/share-networks/sn-1")
    assert resp.status_code == 204
