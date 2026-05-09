"""Manila file_storage / access-rule cross-project IDOR 거부 검증.

afterglow 가 share metadata.union_project_id 로 owner 추적 — 다른 프로젝트의
share_id 로 detail/delete + access-rule 조작 시 404.
"""

from unittest.mock import patch

import pytest

from app.models.storage import FileStorageInfo


def _foreign_share(fs_id: str = "share-foreign", owner: str = "other-project-999"):
    return FileStorageInfo(
        id=fs_id,
        name="foreign",
        status="available",
        size=10,
        share_proto="NFS",
        export_locations=[],
        metadata={"union_project_id": owner},
        project_id=owner,
        created_at="2024-01-01T00:00:00Z",
        nfs_export_location=None,
        library_name=None,
        library_version=None,
        built_at=None,
        is_public=False,
    )


@pytest.mark.asyncio
async def test_get_share_other_project_returns_404(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_foreign_share()):
        resp = await client.get("/api/file-storage/share-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_share_other_project_returns_404(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_foreign_share()):
        resp = await client.delete("/api/file-storage/share-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_delete_other_project_share(admin_client, mock_conn):
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_foreign_share()),
        patch("app.api.storage.file_storage.manila.delete_file_storage", return_value=None),
        patch("app.api.storage.file_storage.invalidate"),
    ):
        resp = await admin_client.delete("/api/file-storage/share-foreign")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_access_rules_other_project_returns_404(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_foreign_share()):
        resp = await client.get("/api/file-storage/share-foreign/access-rules")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_access_rule_other_project_returns_404(client, mock_conn):
    """가장 위험 — 다른 프로젝트 share 에 IP rule 추가하면 cross-tenant CephFS mount 가능."""
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_foreign_share()):
        resp = await client.post(
            "/api/file-storage/share-foreign/access-rules",
            json={"access_to": "10.0.0.0/24", "access_level": "rw", "access_type": "ip"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_access_rule_other_project_returns_404(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_foreign_share()):
        resp = await client.delete("/api/file-storage/share-foreign/access-rules/rule-1")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_share_access_passes_for_get(client, mock_conn):
    """is_public 인 share 는 cross-project 노출이 정상."""
    public = _foreign_share()
    public.is_public = True
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=public):
        resp = await client.get("/api/file-storage/share-foreign")
    assert resp.status_code == 200
