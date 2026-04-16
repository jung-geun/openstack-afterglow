"""볼륨 API 테스트."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app


def make_mock_volume(vol_id: str = "vol-1", name: str = "test-vol", status: str = "available"):
    from app.models.storage import VolumeInfo
    return VolumeInfo(id=vol_id, name=name, status=status, size=10, volume_type=None, attachments=[])


@pytest.mark.asyncio
async def test_list_volumes(client, mock_conn):
    with patch("app.api.storage.volumes.cinder.list_volumes", return_value=[make_mock_volume()]):
        resp = await client.get("/api/volumes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "vol-1"


@pytest.mark.asyncio
async def test_create_volume(client, mock_conn):
    with patch("app.api.storage.volumes.cinder.create_empty_volume", return_value=make_mock_volume("vol-new", "new-vol")):
        resp = await client.post("/api/volumes", json={"name": "new-vol", "size_gb": 10})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_volume(client, mock_conn):
    with patch("app.api.storage.volumes.cinder.delete_volume", return_value=None):
        resp = await client.delete("/api/volumes/vol-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_volume(client, mock_conn):
    with patch("app.api.storage.volumes.cinder.get_volume", return_value=make_mock_volume()):
        resp = await client.get("/api/volumes/vol-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "vol-1"


@pytest.mark.asyncio
async def test_list_volumes_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/volumes")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_transfers_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/volumes/transfers")
    assert resp.status_code == 401



@pytest.mark.asyncio
async def test_create_transfer_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/volumes/vol-1/transfer", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_transfer_success(client):
    with patch("app.api.storage.volumes.cinder") as mock_cinder:
        mock_cinder.create_volume_transfer.return_value = {
            "id": "tr-1", "name": "transfer-1", "volume_id": "vol-1",
            "auth_key": "abc123", "created_at": None,
        }
        resp = await client.post("/api/volumes/vol-1/transfer", json={})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_accept_transfer_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/volumes/transfer/tr-1/accept", json={"auth_key": "abc123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_transfer_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/volumes/transfer/tr-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_transfer_success(client):
    with patch("app.api.storage.volumes.cinder") as mock_cinder:
        mock_cinder.delete_volume_transfer.return_value = None
        resp = await client.delete("/api/volumes/transfer/tr-1")
    assert resp.status_code in (200, 204)
