"""POST /api/file-storage/{id}/access-rules NFS metadata 전달 테스트 (§3.3).

ip 타입 access rule 생성 시 root_squash/sec_flavor metadata가 Manila에 전달되고,
cephx 타입에는 metadata가 전달되지 않음을 검증.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.storage import FileStorageInfo


def _owned_share() -> FileStorageInfo:
    return FileStorageInfo(
        id="share-1",
        name="s",
        status="available",
        size=10,
        share_proto="NFS",
        export_locations=[],
        metadata={"union_project_id": "test-project-123"},
        project_id="test-project-123",
        created_at="2024-01-01T00:00:00Z",
        nfs_export_location=None,
        library_name=None,
        library_version=None,
        built_at=None,
        is_public=False,
    )


@pytest.mark.asyncio
async def test_ip_rule_includes_nfs_metadata(client):
    """access_type=ip 로 rule 생성 시 root_squash/auth_flavor_list metadata가 전달된다."""
    mock_create = MagicMock(
        return_value={"access_id": "rule-1", "access_key": "", "access_to": "10.0.0.0/24", "access_level": "ro"}
    )
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_owned_share()),
        patch("app.api.storage.file_storage.manila.create_access_rule", mock_create),
    ):
        resp = await client.post(
            "/api/file-storage/share-1/access-rules",
            json={"access_to": "10.0.0.0/24", "access_level": "ro", "access_type": "ip"},
        )
    assert resp.status_code == 201
    # metadata 인자가 실제로 전달되었는지 확인
    all_kwargs = mock_create.call_args[1]
    assert "metadata" in all_kwargs, f"metadata 인자 미전달: {mock_create.call_args}"
    meta = all_kwargs["metadata"]
    assert meta is not None
    assert "root_squash" in meta or "auth_flavor_list" in meta


@pytest.mark.asyncio
async def test_ip_rule_custom_root_squash_false(client):
    """root_squash=False 요청 시 metadata에 root_squash 키가 없다 (False 시 빌더가 키 제외)."""
    mock_create = MagicMock(
        return_value={"access_id": "rule-2", "access_key": "", "access_to": "10.0.0.0/24", "access_level": "rw"}
    )
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_owned_share()),
        patch("app.api.storage.file_storage.manila.create_access_rule", mock_create),
    ):
        resp = await client.post(
            "/api/file-storage/share-1/access-rules",
            json={"access_to": "10.0.0.0/24", "access_level": "rw", "access_type": "ip", "root_squash": False},
        )
    assert resp.status_code == 201
    meta = mock_create.call_args[1].get("metadata") or {}
    assert "root_squash" not in meta


@pytest.mark.asyncio
async def test_cephx_rule_no_metadata(client):
    """access_type=cephx 로 rule 생성 시 metadata가 전달되지 않는다."""
    mock_create = MagicMock(
        return_value={"access_id": "rule-3", "access_key": "secret", "access_to": "cephx-id", "access_level": "ro"}
    )
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=_owned_share()),
        patch("app.api.storage.file_storage.manila.create_access_rule", mock_create),
    ):
        resp = await client.post(
            "/api/file-storage/share-1/access-rules",
            json={"access_to": "cephx-id", "access_level": "ro", "access_type": "cephx"},
        )
    assert resp.status_code == 201
    meta = mock_create.call_args[1].get("metadata")
    assert meta is None, f"cephx rule에 metadata가 전달되면 안 됩니다: {meta}"


@pytest.mark.asyncio
async def test_ensure_nfs_access_rule_extra_metadata_merged():
    """ensure_nfs_access_rule이 extra_metadata를 base metadata와 합쳐서 create_access_rule에 전달한다."""
    from app.services.manila import ensure_nfs_access_rule

    mock_create = MagicMock(
        return_value={"access_id": "rule-x", "access_key": "", "access_to": "10.0.0.0/24", "access_level": "ro"}
    )
    mock_list = MagicMock(return_value=[])  # 기존 rule 없음

    conn = MagicMock()
    with (
        patch("app.services.manila.list_access_rules", mock_list),
        patch("app.services.manila.create_access_rule", mock_create),
    ):
        ensure_nfs_access_rule(
            conn,
            "share-1",
            "10.0.0.0/24",
            "ro",
            root_squash=True,
            sec_flavor="sys",
            extra_metadata={"union_grant_project": "proj-b"},
        )

    meta = mock_create.call_args[1].get("metadata") or mock_create.call_args[0][5]
    assert meta is not None
    assert meta.get("union_grant_project") == "proj-b"
    # base metadata도 포함되어야 함
    assert "root_squash" in meta or "auth_flavor_list" in meta


@pytest.mark.asyncio
async def test_ensure_nfs_access_rule_idempotent_returns_existing():
    """이미 동일 access rule이 있으면 create_access_rule을 호출하지 않고 기존 rule을 반환한다."""
    from app.services.manila import ensure_nfs_access_rule

    existing = [
        {
            "id": "existing-rule-1",
            "access_type": "ip",
            "access_to": "10.0.0.0/24",
            "access_level": "ro",
            "state": "active",
        }
    ]
    mock_list = MagicMock(return_value=existing)
    mock_create = MagicMock()

    conn = MagicMock()
    with (
        patch("app.services.manila.list_access_rules", mock_list),
        patch("app.services.manila.create_access_rule", mock_create),
    ):
        result = ensure_nfs_access_rule(conn, "share-1", "10.0.0.0/24", "ro")

    mock_create.assert_not_called()
    assert result["access_id"] == "existing-rule-1"
