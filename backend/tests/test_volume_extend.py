"""볼륨 용량 확장 endpoint 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.storage import VolumeInfo


def _make_volume(size: int = 50) -> MagicMock:
    vol = MagicMock()
    vol.project_id = "test-project-123"
    vol.tenant_id = None
    vol.size = size
    vol.name = "test-vol"
    vol.id = "vol-extend-1"
    vol.status = "available"
    vol.attachments = []
    return vol


def _make_volume_info(size: int = 60) -> VolumeInfo:
    return VolumeInfo(id="vol-extend-1", name="test-vol", status="extending", size=size, attachments=[])


@pytest.mark.asyncio
async def test_extend_volume_happy_path(client, mock_conn):
    mock_conn.block_storage.get_volume.return_value = _make_volume(size=50)
    with (
        patch("app.api.storage.volumes.cinder.extend_volume") as mock_extend,
        patch("app.api.storage.volumes.cinder.get_volume", return_value=_make_volume_info(60)),
        patch("app.api.storage.volumes.rec", new_callable=AsyncMock),
        patch("app.api.storage.volumes.invalidate", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/volumes/vol-extend-1/extend", json={"new_size": 60})

    assert resp.status_code == 200
    mock_extend.assert_called_once_with(mock_conn, "vol-extend-1", 60)
    assert resp.json()["size"] == 60


@pytest.mark.asyncio
async def test_extend_volume_smaller_size_returns_400(client, mock_conn):
    mock_conn.block_storage.get_volume.return_value = _make_volume(size=50)
    with (
        patch("app.api.storage.volumes.cinder.extend_volume") as mock_extend,
        patch("app.api.storage.volumes.rec", new_callable=AsyncMock),
        patch("app.api.storage.volumes.invalidate", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/volumes/vol-extend-1/extend", json={"new_size": 30})

    assert resp.status_code == 400
    assert "30GB" in resp.json()["detail"]
    assert "50GB" in resp.json()["detail"]
    mock_extend.assert_not_called()


@pytest.mark.asyncio
async def test_extend_volume_same_size_returns_400(client, mock_conn):
    mock_conn.block_storage.get_volume.return_value = _make_volume(size=50)
    with (
        patch("app.api.storage.volumes.cinder.extend_volume") as mock_extend,
        patch("app.api.storage.volumes.rec", new_callable=AsyncMock),
        patch("app.api.storage.volumes.invalidate", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/volumes/vol-extend-1/extend", json={"new_size": 50})

    assert resp.status_code == 400
    mock_extend.assert_not_called()


@pytest.mark.asyncio
async def test_extend_volume_not_found_returns_404(client, mock_conn):
    from openstack.exceptions import ResourceNotFound

    mock_conn.block_storage.get_volume.side_effect = ResourceNotFound()
    resp = await client.post("/api/volumes/vol-missing/extend", json={"new_size": 60})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_extend_volume_sdk_error_returns_400(client, mock_conn):
    mock_conn.block_storage.get_volume.return_value = _make_volume(size=50)
    with (
        patch("app.api.storage.volumes.cinder.extend_volume", side_effect=Exception("quota exceeded")),
        patch("app.api.storage.volumes.rec", new_callable=AsyncMock),
        patch("app.api.storage.volumes.invalidate", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/volumes/vol-extend-1/extend", json={"new_size": 60})

    assert resp.status_code == 400
    assert "quota exceeded" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_extend_volume_zero_size_returns_422(client):
    resp = await client.post("/api/volumes/vol-extend-1/extend", json={"new_size": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_extend_volume_negative_size_returns_422(client):
    resp = await client.post("/api/volumes/vol-extend-1/extend", json={"new_size": -10})
    assert resp.status_code == 422
