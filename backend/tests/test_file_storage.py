"""파일 스토리지 API 단위 테스트."""
import pytest
from unittest.mock import patch
from app.models.storage import FileStorageInfo


def make_file_storage(fs_id: str = "share-1", name: str = "test-share") -> FileStorageInfo:
    return FileStorageInfo(
        id=fs_id,
        name=name,
        status="available",
        size=100,
        share_proto="NFS",
        export_locations=[],
        metadata={},
        project_id="test-project-123",
        created_at="2024-01-01T00:00:00Z",
        nfs_export_location=None,
        library_name=None,
        library_version=None,
        built_at=None,
    )


def make_access_rule(rule_id: str = "rule-1") -> dict:
    return {
        "id": rule_id,
        "access_type": "ip",
        "access_to": "10.0.0.0/24",
        "access_level": "rw",
        "state": "active",
    }


@pytest.mark.asyncio
async def test_list_file_storages(client, mock_conn):
    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    with patch("app.api.storage.file_storage.manila.list_file_storages", return_value=[make_file_storage()]), \
         patch("app.api.storage.file_storage.cached_call", new=mock_cached_call):
        resp = await client.get("/api/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["id"] == "share-1"


@pytest.mark.asyncio
async def test_get_file_storage(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()):
        resp = await client.get("/api/file-storage/share-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "share-1"


@pytest.mark.asyncio
async def test_create_file_storage(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.create_file_storage", return_value=make_file_storage("share-new")):
        resp = await client.post("/api/file-storage", json={
            "name": "test-share",
            "size_gb": 100,
            "share_type": "default",
            "share_proto": "NFS",
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_file_storage(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.delete_file_storage", return_value=None), \
         patch("app.api.storage.file_storage.invalidate"):
        resp = await client.delete("/api/file-storage/share-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_access_rules(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.list_access_rules", return_value=[make_access_rule()]):
        resp = await client.get("/api/file-storage/share-1/access-rules")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_access_rule(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.create_access_rule", return_value=make_access_rule("rule-new")):
        resp = await client.post("/api/file-storage/share-1/access-rules", json={
            "access_to": "10.0.0.0/24",
            "access_level": "rw",
            "access_type": "ip",
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_revoke_access_rule(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.revoke_access_rule", return_value=None):
        resp = await client.delete("/api/file-storage/share-1/access-rules/rule-1")
    assert resp.status_code == 204
