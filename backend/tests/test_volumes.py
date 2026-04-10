"""볼륨 API 테스트."""
import pytest
from unittest.mock import MagicMock, patch


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
