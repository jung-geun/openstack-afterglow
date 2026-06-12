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
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.delete_file_storage", return_value=None),
        patch("app.api.storage.file_storage.invalidate"),
    ):
        resp = await client.delete("/api/file-storage/share-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_access_rules(client, mock_conn):
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.list_access_rules", return_value=[make_access_rule()]),
    ):
        resp = await client.get("/api/file-storage/share-1/access-rules")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_access_rule(client, mock_conn):
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.create_access_rule", return_value=make_access_rule("rule-new")),
    ):
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
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.revoke_access_rule", return_value=None),
    ):
        resp = await client.delete("/api/file-storage/share-1/access-rules/rule-1")
    assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────
# CephFS share_network_id 차단 테스트
# ─────────────────────────────────────────────────────────────────


def test_create_file_storage_cephfs_omits_share_network():
    """manila.create_file_storage: CephFS 일 때 share_network_id 를 share_body 에 포함하지 않는다."""
    from unittest.mock import MagicMock

    from app.services import manila as manila_svc

    captured: dict = {}

    fake_client = MagicMock()
    fake_client.post.side_effect = lambda path, body: (
        captured.update({"body": body}) or {"share": {"id": "s1", "status": "available"}}
    )
    fake_client.get.return_value = {
        "share": {
            "id": "s1",
            "name": "f",
            "status": "available",
            "share_proto": "CEPHFS",
            "size": 10,
            "export_locations": [],
            "metadata": {},
            "is_public": False,
            "project_id": "test-project-123",
            "created_at": "2024-01-01T00:00:00Z",
        }
    }

    with patch("app.services.manila.get_client", return_value=fake_client):
        with patch("time.sleep"):
            manila_svc.create_file_storage(
                conn=MagicMock(),
                name="f",
                size_gb=10,
                share_network_id="net-uuid",
                share_proto="CEPHFS",
            )

    assert "share_network_id" not in captured["body"]["share"]


def _make_nfs_share_response(share_id: str = "s2") -> dict:
    return {
        "share": {
            "id": share_id,
            "name": "f",
            "status": "available",
            "share_proto": "NFS",
            "size": 10,
            "export_locations": [],
            "metadata": {},
            "is_public": False,
            "project_id": "test-project-123",
            "created_at": "2024-01-01T00:00:00Z",
        }
    }


def test_create_file_storage_nfs_includes_share_network_when_dhss_true():
    """manila.create_file_storage: DHSS=True share type + NFS → share_network_id 를 share_body 에 포함한다."""
    from app.services import manila as manila_svc

    captured: dict = {}
    fake_client = MagicMock()
    fake_client.post.side_effect = lambda path, body: (
        captured.update({"body": body}) or {"share": {"id": "s2", "status": "available"}}
    )
    fake_client.get.return_value = _make_nfs_share_response()

    dhss_true_type = [
        {
            "id": "t1",
            "name": "nfstype",
            "extra_specs": {"driver_handles_share_servers": "True"},
            "supported_protocols": ["NFS"],
        }
    ]

    with patch("app.services.manila.get_client", return_value=fake_client):
        with patch("time.sleep"):
            with patch("app.services.manila.list_share_types", return_value=dhss_true_type):
                manila_svc.create_file_storage(
                    conn=MagicMock(),
                    name="f",
                    size_gb=10,
                    share_network_id="net-uuid",
                    share_type="nfstype",
                    share_proto="NFS",
                )

    assert captured["body"]["share"]["share_network_id"] == "net-uuid"


def test_create_file_storage_nfs_omits_share_network_when_dhss_false():
    """manila.create_file_storage: DHSS=False share type + NFS → share_network_id 무시."""
    from app.services import manila as manila_svc

    captured: dict = {}
    fake_client = MagicMock()
    fake_client.post.side_effect = lambda path, body: (
        captured.update({"body": body}) or {"share": {"id": "s3", "status": "available"}}
    )
    fake_client.get.return_value = _make_nfs_share_response("s3")

    dhss_false_type = [
        {
            "id": "t2",
            "name": "nfstype",
            "extra_specs": {"driver_handles_share_servers": "False"},
            "supported_protocols": ["NFS"],
        }
    ]

    with patch("app.services.manila.get_client", return_value=fake_client):
        with patch("time.sleep"):
            with patch("app.services.manila.list_share_types", return_value=dhss_false_type):
                manila_svc.create_file_storage(
                    conn=MagicMock(),
                    name="f",
                    size_gb=10,
                    share_network_id="net-uuid",
                    share_type="nfstype",
                    share_proto="NFS",
                )

    assert "share_network_id" not in captured["body"]["share"]


def test_create_file_storage_nfs_includes_share_network_on_type_lookup_failure():
    """list_share_types 조회 실패 시 보수적 fallback: share_network_id 포함."""
    from app.services import manila as manila_svc

    captured: dict = {}
    fake_client = MagicMock()
    fake_client.post.side_effect = lambda path, body: (
        captured.update({"body": body}) or {"share": {"id": "s4", "status": "available"}}
    )
    fake_client.get.return_value = _make_nfs_share_response("s4")

    with patch("app.services.manila.get_client", return_value=fake_client):
        with patch("time.sleep"):
            with patch("app.services.manila.list_share_types", side_effect=Exception("conn fail")):
                manila_svc.create_file_storage(
                    conn=MagicMock(),
                    name="f",
                    size_gb=10,
                    share_network_id="net-uuid",
                    share_type="nfstype",
                    share_proto="NFS",
                )

    assert captured["body"]["share"]["share_network_id"] == "net-uuid"


def test_create_file_storage_error_status_deletes_share_and_raises():
    """폴링 중 error 상태 → share 삭제 호출 + RuntimeError."""
    from app.services import manila as manila_svc

    fake_client = MagicMock()
    fake_client.post.return_value = {"share": {"id": "s5", "status": "creating"}}

    # 첫 폴링 → error; messages API; 두 번째 get → share 상세(delete 이후)
    error_share = {
        "share": {
            "id": "s5",
            "name": "f",
            "status": "error",
            "share_proto": "NFS",
            "size": 10,
            "export_locations": [],
            "metadata": {},
            "is_public": False,
            "project_id": "test-project-123",
            "created_at": "2024-01-01T00:00:00Z",
        }
    }
    # get 호출 순서: 폴링 get → error 감지 → messages get → (delete) → 끝
    fake_client.get.side_effect = [
        error_share,  # 폴링 시 status=error
        {"messages": [{"user_message": "No valid host"}]},  # messages API
    ]
    fake_client.delete = MagicMock()

    dhss_false_type = [
        {
            "id": "t2",
            "name": "nfstype",
            "extra_specs": {"driver_handles_share_servers": "False"},
            "supported_protocols": ["NFS"],
        }
    ]

    with patch("app.services.manila.get_client", return_value=fake_client):
        with patch("time.sleep"):
            with patch("app.services.manila.list_share_types", return_value=dhss_false_type):
                with pytest.raises(RuntimeError) as exc_info:
                    manila_svc.create_file_storage(
                        conn=MagicMock(),
                        name="f",
                        size_gb=10,
                        share_network_id="",
                        share_type="nfstype",
                        share_proto="NFS",
                    )

    assert "error" in str(exc_info.value).lower()
    # share 삭제가 호출됐는지 확인
    fake_client.delete.assert_called_once_with("shares/s5")


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


# ─────────────────────────────────────────────────────────────────
# share_type ↔ share_proto 매칭 / Manila 에러 표면화
# ─────────────────────────────────────────────────────────────────


def test_list_share_types_includes_supported_protocols():
    """list_share_types 가 extra_specs.storage_protocol 을 supported_protocols 로 노출."""
    from unittest.mock import MagicMock

    from app.services import manila as manila_svc

    fake_client = MagicMock()
    fake_client.get.return_value = {
        "share_types": [
            {
                "id": "t1",
                "name": "cephfstype",
                "share_type_access:is_public": True,
                "extra_specs": {"storage_protocol": "CEPHFS", "vendor_name": "Ceph"},
            }
        ]
    }
    with patch("app.services.manila.get_client", return_value=fake_client):
        types = manila_svc.list_share_types(MagicMock())

    assert types[0]["name"] == "cephfstype"
    assert types[0]["supported_protocols"] == ["CEPHFS"]
    assert types[0]["extra_specs"]["vendor_name"] == "Ceph"


def test_list_share_types_falls_back_to_vendor_name():
    """storage_protocol 이 없으면 vendor_name / 이름 패턴으로 추정."""
    from unittest.mock import MagicMock

    from app.services import manila as manila_svc

    fake_client = MagicMock()
    fake_client.get.return_value = {
        "share_types": [
            {
                "id": "t-ceph",
                "name": "any-name",
                "share_type_access:is_public": True,
                "extra_specs": {"vendor_name": "Ceph"},
            },
            {
                "id": "t-nfs",
                "name": "generic-nfs",
                "share_type_access:is_public": False,
                "extra_specs": {"vendor_name": "Generic"},
            },
            {
                "id": "t-unknown",
                "name": "weird",
                "share_type_access:is_public": True,
                "extra_specs": {},
            },
        ]
    }
    with patch("app.services.manila.get_client", return_value=fake_client):
        types = manila_svc.list_share_types(MagicMock())

    by_id = {t["id"]: t for t in types}
    assert by_id["t-ceph"]["supported_protocols"] == ["CEPHFS"]
    assert by_id["t-nfs"]["supported_protocols"] == ["NFS"]
    assert by_id["t-unknown"]["supported_protocols"] == []


def _make_manila_status_error(status: int, message: str) -> "Exception":
    """테스트용 httpx.HTTPStatusError 생성."""
    import httpx

    request = httpx.Request("POST", "http://manila.test/v2/p/shares")
    response = httpx.Response(status, request=request, json={"badRequest": {"code": status, "message": message}})
    return httpx.HTTPStatusError("error", request=request, response=response)


@pytest.mark.asyncio
async def test_create_file_storage_propagates_manila_400(client, mock_conn):
    """Manila 400 → HTTPException 400 + Manila message 그대로 detail 에 포함."""
    err = _make_manila_status_error(400, "Invalid share protocol provided: NFS. Available protocols: ['CEPHFS'].")
    with patch("app.api.storage.file_storage.manila.create_file_storage", side_effect=err):
        resp = await client.post(
            "/api/file-storage",
            json={
                "name": "test-bad",
                "size_gb": 10,
                "share_type": "cephfstype",
                "share_proto": "NFS",
            },
        )
    assert resp.status_code == 400
    assert "Invalid share protocol" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_file_storage_500_fallback(client, mock_conn):
    """일반 Exception 은 여전히 500 으로 (detail 은 글로벌 핸들러가 마스킹)."""
    with patch(
        "app.api.storage.file_storage.manila.create_file_storage",
        side_effect=RuntimeError("boom"),
    ):
        resp = await client.post(
            "/api/file-storage",
            json={
                "name": "test-runtime",
                "size_gb": 10,
                "share_type": "default",
                "share_proto": "CEPHFS",
            },
        )
    # Manila 가 아닌 일반 RuntimeError 는 httpx.HTTPStatusError 분기에 잡히지 않고
    # 일반 Exception 분기로 떨어져 500 으로 변환되어야 한다.
    assert resp.status_code == 500
