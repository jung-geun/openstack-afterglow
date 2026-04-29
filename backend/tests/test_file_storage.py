"""파일 스토리지 API 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.storage import FileStorageInfo
from app.services.manila import _get_manila_endpoint, _normalize_manila_url


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

    with (
        patch("app.api.storage.file_storage.manila.list_file_storages", return_value=[make_file_storage()]),
        patch("app.api.storage.file_storage.cached_call", new=mock_cached_call),
    ):
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
        resp = await client.post(
            "/api/file-storage",
            json={
                "name": "test-share",
                "size_gb": 100,
                "share_type": "default",
                "share_proto": "NFS",
            },
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_file_storage(client, mock_conn):
    with (
        patch("app.api.storage.file_storage.manila.delete_file_storage", return_value=None),
        patch("app.api.storage.file_storage.invalidate"),
    ):
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
        resp = await client.post(
            "/api/file-storage/share-1/access-rules",
            json={
                "access_to": "10.0.0.0/24",
                "access_level": "rw",
                "access_type": "ip",
            },
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_revoke_access_rule(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.revoke_access_rule", return_value=None):
        resp = await client.delete("/api/file-storage/share-1/access-rules/rule-1")
    assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────
# Manila endpoint 정규화 단위 테스트 (회귀 방지)
# ─────────────────────────────────────────────────────────────────


def test_normalize_manila_url_replaces_v1_with_v2():
    assert _normalize_manila_url("https://manila.example.com/v1/abc") == "https://manila.example.com/v2/abc"
    assert _normalize_manila_url("https://manila.example.com/v2/abc") == "https://manila.example.com/v2/abc"
    # v10 같은 경계 케이스 — v1 토큰만 치환하고 v10 등은 건드리지 않는다
    assert _normalize_manila_url("https://manila.example.com/v10/abc") == "https://manila.example.com/v10/abc"
    # 경로 끝에 v1 이 오는 경우
    assert _normalize_manila_url("https://manila.example.com/v1") == "https://manila.example.com/v2"


def test_get_manila_endpoint_prefers_sharev2_over_share():
    """openstacksdk catalog 에 share(v1)/sharev2(v2) 둘 다 있을 때 v2 우선 선택 검증."""
    conn = MagicMock()

    def endpoint_for(service_type, interface=None):
        if service_type == "sharev2":
            return "https://manila.example.com/v2/proj-1"
        if service_type == "share":
            return "https://manila.example.com/v1/proj-1"
        raise Exception("not found")

    conn.endpoint_for.side_effect = endpoint_for
    assert _get_manila_endpoint(conn) == "https://manila.example.com/v2/proj-1"


def test_get_manila_endpoint_normalizes_v1_fallback():
    """sharev2 가 없고 share(v1) 만 있어도 v2 path 로 정규화."""
    conn = MagicMock()

    def endpoint_for(service_type, interface=None):
        if service_type == "share":
            return "https://manila.example.com/v1/proj-1"
        raise Exception("not found")

    conn.endpoint_for.side_effect = endpoint_for
    assert _get_manila_endpoint(conn) == "https://manila.example.com/v2/proj-1"


# ─────────────────────────────────────────────────────────────────
# 프로젝트 격리 테스트
# ─────────────────────────────────────────────────────────────────


def _make_share_other_project(is_public: bool = False) -> FileStorageInfo:
    """다른 프로젝트(project-B)가 소유한 동적 share."""
    return FileStorageInfo(
        id="share-other",
        name="other-share",
        status="available",
        size=10,
        share_proto="CEPHFS",
        metadata={"union_type": "dynamic", "union_project_id": "project-B"},
        is_public=is_public,
    )


@pytest.mark.asyncio
async def test_list_file_storages_filters_other_project(client, mock_conn):
    """non-admin이 list 요청 시 다른 프로젝트의 private dynamic share는 미수신."""
    own = make_file_storage("share-mine")
    own.metadata["union_project_id"] = "test-project-123"
    other = _make_share_other_project(is_public=False)
    all_shares = [own, other]

    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    def mock_list(conn, metadata_filter=None, all_tenants=False, caller_project_id=None):
        if caller_project_id:
            return [
                s
                for s in all_shares
                if s.is_public or s.metadata.get("union_project_id") in (caller_project_id, None, "")
            ]
        return all_shares

    with (
        patch("app.api.storage.file_storage.manila.list_file_storages", side_effect=mock_list),
        patch("app.api.storage.file_storage.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/file-storage")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert "share-mine" in ids
    assert "share-other" not in ids


@pytest.mark.asyncio
async def test_list_file_storages_exposes_public_share(client, mock_conn):
    """is_public=True인 prebuilt share는 다른 프로젝트도 list에서 수신."""
    public_share = _make_share_other_project(is_public=True)

    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    def mock_list(conn, metadata_filter=None, all_tenants=False, caller_project_id=None):
        if caller_project_id:
            return [
                s
                for s in [public_share]
                if s.is_public or s.metadata.get("union_project_id") in (caller_project_id, None, "")
            ]
        return [public_share]

    with (
        patch("app.api.storage.file_storage.manila.list_file_storages", side_effect=mock_list),
        patch("app.api.storage.file_storage.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/file-storage")
    assert resp.status_code == 200
    assert any(s["id"] == "share-other" for s in resp.json())


@pytest.mark.asyncio
async def test_get_file_storage_cross_project_returns_404(client, mock_conn):
    """non-admin이 다른 프로젝트 share를 직접 ID로 GET 시 404."""
    other = _make_share_other_project(is_public=False)
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=other):
        resp = await client.get("/api/file-storage/share-other")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_get_cross_project_share(admin_client, mock_conn):
    """admin은 다른 프로젝트 share도 GET 가능."""
    other = _make_share_other_project(is_public=False)
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=other):
        resp = await admin_client.get("/api/file-storage/share-other")
    assert resp.status_code == 200
