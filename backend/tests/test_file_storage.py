"""파일 스토리지 API 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.storage import FileStorageInfo
from app.services.manila import _get_manila_endpoint, _normalize_manila_url, _parse_file_storage


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
        resp = await client.get("/api/v1/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["id"] == "share-1"


@pytest.mark.asyncio
async def test_get_file_storage(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()):
        resp = await client.get("/api/v1/file-storage/share-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "share-1"


@pytest.mark.asyncio
async def test_create_file_storage(client, mock_conn):
    with patch("app.api.storage.file_storage.manila.create_file_storage", return_value=make_file_storage("share-new")):
        resp = await client.post(
            "/api/v1/file-storage",
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
        resp = await client.delete("/api/v1/file-storage/share-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_access_rules(client, mock_conn):
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.list_access_rules", return_value=[make_access_rule()]),
    ):
        resp = await client.get("/api/v1/file-storage/share-1/access-rules")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_access_rule(client, mock_conn):
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.create_access_rule", return_value=make_access_rule("rule-new")),
    ):
        resp = await client.post(
            "/api/v1/file-storage/share-1/access-rules",
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
        resp = await client.delete("/api/v1/file-storage/share-1/access-rules/rule-1")
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
        resp = await client.get("/api/v1/file-storage")
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
        resp = await client.get("/api/v1/file-storage")
    assert resp.status_code == 200
    assert any(s["id"] == "share-other" for s in resp.json())


@pytest.mark.asyncio
async def test_get_file_storage_cross_project_returns_404(client, mock_conn):
    """non-admin이 다른 프로젝트 share를 직접 ID로 GET 시 404."""
    other = _make_share_other_project(is_public=False)
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=other):
        resp = await client.get("/api/v1/file-storage/share-other")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_get_cross_project_share(admin_client, mock_conn):
    """admin은 다른 프로젝트 share도 GET 가능."""
    other = _make_share_other_project(is_public=False)
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=other):
        resp = await admin_client.get("/api/v1/file-storage/share-other")
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
            "/api/v1/file-storage",
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
async def test_create_file_storage_runtime_error_returns_409(client, mock_conn):
    """Manila 폴링 RuntimeError (capabilities filter 등) → 409 + 사유 detail 노출."""
    with patch(
        "app.api.storage.file_storage.manila.create_file_storage",
        side_effect=RuntimeError("파일 스토리지 생성 실패 (error 상태): Capabilities filter didn't succeed."),
    ):
        resp = await client.post(
            "/api/v1/file-storage",
            json={
                "name": "test-cap-fail",
                "size_gb": 10,
                "share_type": "nfstype",
                "share_proto": "NFS",
            },
        )
    assert resp.status_code == 409
    assert "Capabilities filter" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_file_storage_500_fallback(client, mock_conn):
    """RuntimeError 가 아닌 일반 Exception 은 여전히 500 으로 (글로벌 핸들러가 마스킹)."""
    with patch(
        "app.api.storage.file_storage.manila.create_file_storage",
        side_effect=ValueError("unexpected"),
    ):
        resp = await client.post(
            "/api/v1/file-storage",
            json={
                "name": "test-valueerr",
                "size_gb": 10,
                "share_type": "default",
                "share_proto": "CEPHFS",
            },
        )
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_create_file_storage_nfs_uses_nfs_share_type_fallback(client, mock_conn):
    """share_type 미지정 + NFS → settings.os_manila_nfs_share_type 으로 fallback (CephFS 타입과 다름)."""
    from app.config import get_settings

    settings = get_settings()
    with patch(
        "app.api.storage.file_storage.manila.create_file_storage", return_value=make_file_storage()
    ) as mock_create:
        resp = await client.post(
            "/api/v1/file-storage",
            json={"name": "nfs-no-type", "size_gb": 10, "share_proto": "NFS"},
        )
    assert resp.status_code == 201
    _, kwargs = mock_create.call_args
    assert kwargs["share_type"] == settings.os_manila_nfs_share_type
    assert kwargs["share_type"] != settings.os_manila_share_type  # NFS ≠ CephFS 타입


@pytest.mark.asyncio
async def test_create_file_storage_cephfs_uses_cephfs_share_type_fallback(client, mock_conn):
    """share_type 미지정 + CEPHFS → settings.os_manila_share_type 으로 fallback."""
    from app.config import get_settings

    settings = get_settings()
    with patch(
        "app.api.storage.file_storage.manila.create_file_storage", return_value=make_file_storage()
    ) as mock_create:
        resp = await client.post(
            "/api/v1/file-storage",
            json={"name": "ceph-no-type", "size_gb": 10, "share_proto": "CEPHFS"},
        )
    assert resp.status_code == 201
    _, kwargs = mock_create.call_args
    assert kwargs["share_type"] == settings.os_manila_share_type


# ─────────────────────────────────────────────────────────────────
# 접근 규칙 생성 — metadata 미전달 + 오류 표면화 + 응답 필드 검증
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_access_rule_no_metadata_passed(client, mock_conn):
    """IP 타입 접근 규칙 생성 시 manila.create_access_rule에 metadata를 전달하지 않는다.

    Manila CephFS는 access rule metadata를 지원하지 않으며 전달 시 400을 반환한다.
    """
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch(
            "app.api.storage.file_storage.manila.create_access_rule", return_value=make_access_rule("rule-ip")
        ) as mock_create,
    ):
        resp = await client.post(
            "/api/v1/file-storage/share-1/access-rules",
            json={"access_to": "10.0.0.0/24", "access_level": "rw", "access_type": "ip"},
        )
    assert resp.status_code == 201
    _, kwargs = mock_create.call_args
    assert "metadata" not in kwargs


@pytest.mark.asyncio
async def test_create_access_rule_response_has_id_field(client, mock_conn):
    """create_access_rule 응답에 'id' 필드가 있어야 한다 (마법사 step 3 keyed #each 바인딩)."""
    rule = make_access_rule("rule-new")
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.create_access_rule", return_value=rule),
    ):
        resp = await client.post(
            "/api/v1/file-storage/share-1/access-rules",
            json={"access_to": "10.0.0.0/24", "access_level": "rw", "access_type": "ip"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["id"] == "rule-new"
    assert "access_type" in data
    assert "state" in data


@pytest.mark.asyncio
async def test_create_access_rule_propagates_manila_400(client, mock_conn):
    """Manila 400 → HTTPException 400 + Manila 메시지가 detail에 포함된다."""
    err = _make_manila_status_error(400, "Access rule already exists.")
    with (
        patch("app.api.storage.file_storage.manila.get_file_storage", return_value=make_file_storage()),
        patch("app.api.storage.file_storage.manila.create_access_rule", side_effect=err),
    ):
        resp = await client.post(
            "/api/v1/file-storage/share-1/access-rules",
            json={"access_to": "10.0.0.0/24", "access_level": "rw", "access_type": "ip"},
        )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────────
# 확장 필드 파싱 테스트 (progress, user_id, access_rules_status 등)
# ─────────────────────────────────────────────────────────────────


def _make_full_share_dict(share_id: str = "s-full") -> dict:
    """Manila share 응답 dict — 확장 필드 포함."""
    return {
        "id": share_id,
        "name": "full-share",
        "status": "available",
        "size": 10,
        "share_proto": "NFS",
        "export_locations": [],  # Manila 2.9+에서 인라인은 항상 빔
        "metadata": {"union_library": "python311", "union_version": "3.11"},
        "is_public": False,
        "project_id": "proj-abc",
        "created_at": "2024-06-01T12:00:00Z",
        "progress": "100%",
        "user_id": "user-uuid-123",
        "access_rules_status": "active",
        "host": "dms-controller1@cephfsnfs1#cephfs",
        "availability_zone": "nova",
        "share_type_name": "cephfsnfstype",
        "share_network_id": "net-uuid-456",
    }


def test_parse_file_storage_extended_fields():
    """_parse_file_storage가 확장 필드를 올바르게 파싱한다."""
    data = _make_full_share_dict()
    fs = _parse_file_storage(data)

    assert fs.progress == "100%"
    assert fs.user_id == "user-uuid-123"
    assert fs.access_rules_status == "active"
    assert fs.host == "dms-controller1@cephfsnfs1#cephfs"
    assert fs.availability_zone == "nova"
    assert fs.share_type_name == "cephfsnfstype"
    assert fs.share_network_id == "net-uuid-456"
    # user_name은 _parse_file_storage 단계에서는 None (resolve 전)
    assert fs.user_name is None
    # export_detail_list 없으면 export_location_details 비어야 함
    assert fs.export_location_details == []


def test_parse_file_storage_export_detail_list():
    """export_detail_list 인자를 주면 export_locations·export_location_details가 채워진다."""
    data = _make_full_share_dict()
    export_details = [
        {"path": "172.30.2.101:/volumes/path", "preferred": True, "share_instance_id": "inst-1"},
        {"path": "172.30.2.102:/volumes/path", "preferred": False, "share_instance_id": "inst-2"},
    ]
    fs = _parse_file_storage(data, export_detail_list=export_details)

    assert len(fs.export_locations) == 2
    assert fs.export_locations[0] == "172.30.2.101:/volumes/path"
    assert len(fs.export_location_details) == 2
    assert fs.export_location_details[0].preferred is True
    assert fs.export_location_details[0].share_instance_id == "inst-1"
    assert fs.export_location_details[1].preferred is False


def test_parse_file_storage_no_export_detail_list_inline_empty():
    """export_detail_list 없으면 인라인 export_locations(항상 빔)를 읽어 빈 리스트 반환."""
    data = _make_full_share_dict()
    data["export_locations"] = []  # Manila 2.9+ 실제 동작
    fs = _parse_file_storage(data)

    assert fs.export_locations == []
    assert fs.export_location_details == []


def test_get_file_storage_merges_export_details():
    """get_file_storage가 export_locations 서브리소스를 병합한다."""
    from app.services import manila as manila_svc

    share_data = _make_full_share_dict()
    export_details = [
        {"path": "172.30.2.101:/vol", "preferred": True, "share_instance_id": "inst-1"},
    ]

    fake_client = MagicMock()
    fake_client.get.side_effect = lambda path: (
        {"share": share_data}
        if path == f"shares/{share_data['id']}"
        else {"export_locations": [{**d, "is_admin_only": False} for d in export_details]}
    )

    with patch("app.services.manila.get_client", return_value=fake_client):
        fs = manila_svc.get_file_storage(MagicMock(), share_data["id"])

    assert len(fs.export_locations) == 1
    assert fs.export_locations[0] == "172.30.2.101:/vol"
    assert fs.export_location_details[0].preferred is True


def test_get_file_storage_export_failure_falls_back_to_empty():
    """export_locations 서브리소스 조회 실패 시 빈 리스트로 fallback."""
    from app.services import manila as manila_svc

    share_data = _make_full_share_dict()

    fake_client = MagicMock()

    def _get(path):
        if "export_locations" in path:
            raise Exception("network error")
        return {"share": share_data}

    fake_client.get.side_effect = _get

    with patch("app.services.manila.get_client", return_value=fake_client):
        fs = manila_svc.get_file_storage(MagicMock(), share_data["id"])

    assert fs.export_locations == []
    assert fs.export_location_details == []


def test_get_file_storage_resolve_user_sets_user_name():
    """resolve_user=True 시 keystone.get_user 성공 → user_name이 채워진다."""
    from app.services import manila as manila_svc

    share_data = _make_full_share_dict()

    fake_client = MagicMock()
    fake_client.get.side_effect = lambda path: (
        {"share": share_data} if "export_locations" not in path else {"export_locations": []}
    )

    with (
        patch("app.services.manila.get_client", return_value=fake_client),
        patch("app.services.keystone.get_user", return_value={"id": "user-uuid-123", "name": "pie_root", "email": ""}),
    ):
        fs = manila_svc.get_file_storage(MagicMock(), share_data["id"], resolve_user=True)

    assert fs.user_name == "pie_root"


def test_get_file_storage_resolve_user_fallback_on_keystone_error():
    """resolve_user=True 시 keystone.get_user 실패 → user_name=None 유지."""
    from app.services import manila as manila_svc

    share_data = _make_full_share_dict()

    fake_client = MagicMock()
    fake_client.get.side_effect = lambda path: (
        {"share": share_data} if "export_locations" not in path else {"export_locations": []}
    )

    with (
        patch("app.services.manila.get_client", return_value=fake_client),
        patch("app.services.keystone.get_user", side_effect=Exception("forbidden")),
    ):
        fs = manila_svc.get_file_storage(MagicMock(), share_data["id"], resolve_user=True)

    assert fs.user_name is None
    assert fs.user_id == "user-uuid-123"  # user_id는 그대로 유지


@pytest.mark.asyncio
async def test_get_file_storage_detail_masks_host_for_non_admin(client, mock_conn):
    """비-admin 사용자 상세 조회 시 host 필드가 None으로 마스킹된다."""
    share_with_host = make_file_storage().model_copy(update={"host": "dms-controller1@cephfsnfs1#cephfs"})
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=share_with_host):
        resp = await client.get("/api/v1/file-storage/share-1")
    assert resp.status_code == 200
    assert resp.json()["host"] is None


@pytest.mark.asyncio
async def test_get_file_storage_detail_exposes_host_for_admin(admin_client, mock_conn):
    """admin 사용자 상세 조회 시 host 필드가 노출된다."""
    share_with_host = make_file_storage().model_copy(update={"host": "dms-controller1@cephfsnfs1#cephfs"})
    with patch("app.api.storage.file_storage.manila.get_file_storage", return_value=share_with_host):
        resp = await admin_client.get("/api/v1/file-storage/share-1")
    assert resp.status_code == 200
    assert resp.json()["host"] == "dms-controller1@cephfsnfs1#cephfs"
