"""볼륨 스냅샷 API 단위 테스트."""
import pytest
from unittest.mock import patch


def make_snapshot(snap_id: str = "snap-1", name: str = "test-snap") -> dict:
    return {
        "id": snap_id,
        "name": name,
        "status": "available",
        "size": 10,
        "volume_id": "vol-1",
        "created_at": "2024-01-01T00:00:00Z",
        "description": None,
    }


@pytest.mark.asyncio
async def test_list_snapshots(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.list_snapshots", return_value=[make_snapshot()]):
        resp = await client.get("/api/volume-snapshots")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["id"] == "snap-1"


@pytest.mark.asyncio
async def test_create_snapshot(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.create_snapshot", return_value=make_snapshot("snap-new")):
        resp = await client.post("/api/volume-snapshots", json={
            "volume_id": "vol-1",
            "name": "test-snap",
            "description": "",
            "force": False,
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_snapshot(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.get_snapshot", return_value=make_snapshot()):
        resp = await client.get("/api/volume-snapshots/snap-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "snap-1"


@pytest.mark.asyncio
async def test_delete_snapshot(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.delete_snapshot", return_value=None):
        resp = await client.delete("/api/volume-snapshots/snap-1")
    assert resp.status_code == 204
