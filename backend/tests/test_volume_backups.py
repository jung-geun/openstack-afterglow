"""볼륨 백업 API 테스트."""
import pytest
from unittest.mock import patch


def make_backup(bid: str = "backup-1"):
    return {
        "id": bid,
        "name": "test-backup",
        "status": "available",
        "volume_id": "vol-1",
        "size": 10,
        "is_incremental": False,
        "description": "",
        "created_at": "2024-01-01T00:00:00",
    }


@pytest.mark.asyncio
async def test_list_backups(client, mock_conn):
    with patch("app.api.storage.volume_backups.cinder.list_backups", return_value=[make_backup()]):
        resp = await client.get("/api/volumes/backups")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "backup-1"


@pytest.mark.asyncio
async def test_create_backup(client, mock_conn):
    with patch("app.api.storage.volume_backups.cinder.create_backup", return_value=make_backup("backup-new")):
        resp = await client.post("/api/volumes/backups", json={
            "volume_id": "vol-1", "name": "my-backup"
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_backup(client, mock_conn):
    with patch("app.api.storage.volume_backups.cinder.delete_backup", return_value=None):
        resp = await client.delete("/api/volumes/backups/backup-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_backup_not_shadowed_by_volumes_route(client, mock_conn):
    """볼륨 라우터가 /backups를 가로채지 않음을 확인 (Task 1 버그 수정)."""
    with patch("app.api.storage.volume_backups.cinder.list_backups", return_value=[make_backup()]):
        resp = await client.get("/api/volumes/backups")
    # 404가 아닌 200이어야 함
    assert resp.status_code == 200
