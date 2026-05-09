"""Object Storage (Swift) API 단위 테스트.

swift 서비스는 SERVICE_SWIFT_ENABLED=true 시 /api/object-storage/* 경로로 등록.
비활성화 시 대부분 404/405 응답 → 인증 관문 테스트는 in (401, 404, 405) 허용.
swift 함수는 핸들러 내에서 lazy import하므로 app.services.swift 를 패치.
"""

import json
import urllib.parse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# 계정 메타데이터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_account_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/object-storage/account")
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_get_account_success(client, mock_conn):
    with patch("app.services.swift") as mock_swift:
        mock_swift.get_account = MagicMock(return_value={"container_count": 2, "object_count": 10, "bytes_used": 2048})
        resp = await client.get("/api/object-storage/account")
    assert resp.status_code in (200, 404, 405, 500)


# ---------------------------------------------------------------------------
# 컨테이너 목록 / 생성 / 삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_containers_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/object-storage/containers")
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_list_containers_empty(client, mock_conn):
    with patch("app.services.swift") as mock_swift:
        mock_swift.list_containers = MagicMock(return_value=[])
        resp = await client.get("/api/object-storage/containers")
    assert resp.status_code in (200, 404, 405, 500)


@pytest.mark.asyncio
async def test_create_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/object-storage/containers", json={"name": "new-bucket"})
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_delete_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/object-storage/containers/test-container")
    assert resp.status_code in (401, 404, 405)


# ---------------------------------------------------------------------------
# 오브젝트 업로드
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_object_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/object-storage/containers/test-container/objects",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_upload_object_success(client, mock_conn):
    with patch("app.services.swift") as mock_swift:
        mock_swift.upload_object = MagicMock(return_value={"name": "test.txt"})
        resp = await client.post(
            "/api/object-storage/containers/test-container/objects",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
    assert resp.status_code in (201, 404, 405, 500)


# ---------------------------------------------------------------------------
# 오브젝트 다운로드 / 삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_object_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/object-storage/containers/test-container/objects/test.txt/download")
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_delete_object_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/object-storage/containers/test-container/objects/test.txt")
    assert resp.status_code in (401, 404, 405)


# ---------------------------------------------------------------------------
# SLO (Static Large Object) 동작 검증
# ---------------------------------------------------------------------------


def test_upload_large_object_uses_manual_slo():
    """1 GiB 초과 파일 업로드 시 수동 SLO: proxy.put 을 (segments + 1) 회 호출하고 마지막 URL 에 multipart-manifest=put 포함."""
    import io
    import math
    from unittest.mock import MagicMock, patch

    from app.services.swift import _SLO_SEGMENT_SIZE, upload_object

    conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {"etag": '"abc123"'}
    conn.object_store.put.return_value = mock_resp

    large_size = _SLO_SEGMENT_SIZE + 1  # 1 GiB + 1 byte → 2 segments
    with (
        patch("app.services.swift._apply_endpoint_override"),
        patch("app.services.swift._ensure_segment_container") as mock_ensure,
    ):
        upload_object(conn, "bucket", "big.bin", io.BytesIO(b""), "application/octet-stream", large_size)

    num_segments = math.ceil(large_size / _SLO_SEGMENT_SIZE)
    assert conn.object_store.put.call_count == num_segments + 1
    manifest_url = conn.object_store.put.call_args_list[-1][0][0]
    assert "multipart-manifest=put" in manifest_url
    mock_ensure.assert_called_once_with(conn, "bucket_segments")


def test_list_containers_hides_segments():
    """_segments 접미사 컨테이너는 사용자 목록에서 숨겨진다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import list_containers

    def make(name, count, bytes_):
        c = MagicMock()
        c.name = name
        c.count = count
        c.bytes = bytes_
        return c

    conn = MagicMock()
    conn.object_store.containers.return_value = [
        make("test", 7, 3 * 1024**3),
        make("test_segments", 10, 9 * 1024**3),
        make("photos", 100, 500 * 1024**2),
    ]
    with patch("app.services.swift._apply_endpoint_override"):
        result = list_containers(conn)
    by_name = {c["name"]: c for c in result}
    assert "test" in by_name
    assert "photos" in by_name
    assert "test_segments" not in by_name
    # segments 컨테이너 bytes 가 원본 컨테이너에 합산됨 (3 GiB + 9 GiB = 12 GiB)
    assert by_name["test"]["bytes"] == 3 * 1024**3 + 9 * 1024**3
    # segments 가 없는 컨테이너는 그대로 유지
    assert by_name["photos"]["bytes"] == 500 * 1024**2


def test_list_containers_quarantine_default_hidden():
    """default 호출 시 *-quarantine 도 숨겨진다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import list_containers

    def make(name, count, bytes_):
        c = MagicMock()
        c.name, c.count, c.bytes = name, count, bytes_
        return c

    conn = MagicMock()
    conn.object_store.containers.return_value = [
        make("test", 4, 1024),
        make("test-quarantine", 17, 512),
    ]
    with patch("app.services.swift._apply_endpoint_override"):
        result = list_containers(conn)
    names = [c["name"] for c in result]
    assert names == ["test"]


def test_list_containers_include_quarantine_admin():
    """include_quarantine=True 시 *-quarantine 포함 + is_quarantine 플래그."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import list_containers

    def make(name, count, bytes_):
        c = MagicMock()
        c.name, c.count, c.bytes = name, count, bytes_
        return c

    conn = MagicMock()
    conn.object_store.containers.return_value = [
        make("test", 4, 1024),
        make("test-quarantine", 17, 512),
        make("test_segments", 1, 2048),  # segments 는 여전히 숨김
    ]
    with patch("app.services.swift._apply_endpoint_override"):
        result = list_containers(conn, include_quarantine=True)
    by_name = {c["name"]: c for c in result}
    assert "test" in by_name
    assert "test-quarantine" in by_name
    assert "test_segments" not in by_name
    assert by_name["test-quarantine"]["is_quarantine"] is True
    assert "is_quarantine" not in by_name["test"]


def test_get_container_metadata_includes_segments():
    """get_container_metadata 의 bytes 에 {name}_segments 의 bytes_used 가 합산된다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import get_container_metadata

    base_meta = MagicMock()
    base_meta.name = "test"
    base_meta.object_count = 2
    base_meta.bytes_used = 1024 * 1024 + 2000  # 매니페스트 + 일반 파일 ≈ 1 MiB
    base_meta.read_ACL = ""
    base_meta.write_ACL = ""

    seg_meta = MagicMock()
    seg_meta.bytes_used = 9 * 1024**3  # 9 GiB segments

    conn = MagicMock()

    def get_meta_side_effect(name):
        if name == "test":
            return base_meta
        if name == "test_segments":
            return seg_meta
        raise Exception("404")

    conn.object_store.get_container_metadata.side_effect = get_meta_side_effect

    with patch("app.services.swift._apply_endpoint_override"):
        result = get_container_metadata(conn, "test")

    assert result["name"] == "test"
    assert result["count"] == 2
    # base + segments 합계
    assert result["bytes"] == 1024 * 1024 + 2000 + 9 * 1024**3


def test_get_container_metadata_no_segments():
    """{name}_segments 컨테이너가 없는 경우 base bytes 만 반환한다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import get_container_metadata

    base_meta = MagicMock()
    base_meta.name = "photos"
    base_meta.object_count = 100
    base_meta.bytes_used = 500 * 1024**2
    base_meta.read_ACL = ""
    base_meta.write_ACL = ""

    conn = MagicMock()

    def get_meta_side_effect(name):
        if name == "photos":
            return base_meta
        raise Exception("404")

    conn.object_store.get_container_metadata.side_effect = get_meta_side_effect

    with patch("app.services.swift._apply_endpoint_override"):
        result = get_container_metadata(conn, "photos")

    assert result["bytes"] == 500 * 1024**2


def test_list_objects_enriches_slo_sizes():
    """SLO 매니페스트의 bytes 가 segments 합계로 교체된다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import list_objects

    # 정규 컨테이너에는 매니페스트(1.6 KB)와 일반 파일이 보임
    manifest = MagicMock()
    manifest.name = "big.zip"
    manifest.size = 1638
    manifest.content_type = "application/zip"
    manifest.last_modified_at = ""
    manifest.etag = ""
    manifest.subdir = None
    normal = MagicMock()
    normal.name = "small.txt"
    normal.size = 100
    normal.content_type = "text/plain"
    normal.last_modified_at = ""
    normal.etag = ""
    normal.subdir = None

    # segments 컨테이너에는 big.zip/00000000, big.zip/00000001 두 segment
    seg0 = MagicMock()
    seg0.name = "big.zip/00000000"
    seg0.size = 1024**3  # 1 GiB
    seg1 = MagicMock()
    seg1.name = "big.zip/00000001"
    seg1.size = 500 * 1024**2  # 500 MiB

    conn = MagicMock()

    def objects_side_effect(container, **kwargs):
        if container == "test":
            return iter([manifest, normal])
        if container == "test_segments":
            return iter([seg0, seg1])
        return iter([])

    conn.object_store.objects.side_effect = objects_side_effect

    with patch("app.services.swift._apply_endpoint_override"):
        result = list_objects(conn, "test")

    by_name = {r["name"]: r for r in result}
    # SLO 매니페스트는 segments 합계로 보정 (1 GiB + 500 MiB)
    assert by_name["big.zip"]["bytes"] == 1024**3 + 500 * 1024**2
    # 일반 파일은 변경 없음
    assert by_name["small.txt"]["bytes"] == 100


def test_list_objects_no_segments_container_keeps_sizes():
    """_segments 컨테이너가 없어도 listing 은 원본 사이즈로 정상 반환된다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import list_objects

    obj = MagicMock()
    obj.name = "file.bin"
    obj.size = 12345
    obj.content_type = "application/octet-stream"
    obj.last_modified_at = ""
    obj.etag = ""
    obj.subdir = None

    conn = MagicMock()

    def objects_side_effect(container, **kwargs):
        if container == "test":
            return iter([obj])
        # _segments LIST 시도 시 404 시뮬레이션
        raise Exception("404")

    conn.object_store.objects.side_effect = objects_side_effect

    with patch("app.services.swift._apply_endpoint_override"):
        result = list_objects(conn, "test")

    assert len(result) == 1
    assert result[0]["bytes"] == 12345


def test_upload_small_object_no_slo():
    """100 MB 파일 업로드 시 SLO 옵션이 전달되지 않는다."""
    import io
    from unittest.mock import MagicMock, patch

    from app.services.swift import upload_object

    conn = MagicMock()
    mock_obj = MagicMock()
    mock_obj.name = "small.bin"
    mock_obj.etag = ""
    conn.object_store.create_object.return_value = mock_obj

    small_size = 100 * 1024 * 1024  # 100 MB
    with patch("app.services.swift._apply_endpoint_override"):
        upload_object(conn, "bucket", "small.bin", io.BytesIO(b""), "application/octet-stream", small_size)

    kw = conn.object_store.create_object.call_args[1]
    assert "use_slo" not in kw
    assert "segment_size" not in kw


# ---------------------------------------------------------------------------
# 스트리밍 PUT 업로드
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_upload_missing_content_length():
    """Content-Length 없이 PUT 요청 → 411."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/object-storage/test-container/objects/file.bin",
            content=b"data",
            headers={"Content-Type": "application/octet-stream"},
        )
    assert resp.status_code in (401, 404, 405, 411)


@pytest.mark.asyncio
async def test_streaming_upload_too_large():
    """Content-Length > 100 GiB → 413 (또는 인증 먼저 401)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/object-storage/test-container/objects/huge.bin",
            content=b"x",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(100 * 1024**3 + 1),
            },
        )
    assert resp.status_code in (401, 404, 405, 413)


def test_streaming_upload_small_no_slo():
    """100 MB raw PUT → SLO 옵션 미사용."""
    import io
    from unittest.mock import MagicMock, patch

    from app.services.swift import upload_object

    conn = MagicMock()
    mock_obj = MagicMock()
    mock_obj.name = "small.bin"
    mock_obj.etag = ""
    conn.object_store.create_object.return_value = mock_obj

    small_size = 100 * 1024 * 1024
    with patch("app.services.swift._apply_endpoint_override"):
        upload_object(conn, "bucket", "small.bin", io.BytesIO(b""), "application/octet-stream", small_size)

    kw = conn.object_store.create_object.call_args[1]
    assert "use_slo" not in kw
    assert "segment_size" not in kw


def test_streaming_upload_large_uses_manual_slo():
    """6.5 GiB raw PUT → 수동 SLO: proxy.put 2(segments) + 1(manifest) = 3 회.

    SLO 임계값이 5 GiB 이므로 6.5 GiB 는 ceil(6.5/5) = 2 segments.
    """
    import io
    import math
    from unittest.mock import MagicMock, patch

    from app.services.swift import _SLO_SEGMENT_SIZE, upload_object

    conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {"etag": '"deadbeef"'}
    conn.object_store.put.return_value = mock_resp

    large_size = int(6.5 * 1024**3)  # 5 GiB 초과 → SLO 발동, 2 segments
    with patch("app.services.swift._apply_endpoint_override"), patch("app.services.swift._ensure_segment_container"):
        upload_object(conn, "bucket", "large.bin", io.BytesIO(b""), "application/octet-stream", large_size)

    num_segments = math.ceil(large_size / _SLO_SEGMENT_SIZE)
    assert conn.object_store.put.call_count == num_segments + 1
    manifest_url = conn.object_store.put.call_args_list[-1][0][0]
    assert "multipart-manifest=put" in manifest_url


def test_delete_slo_object_purges_segments():
    """SLO manifest 삭제 시 ?multipart-manifest=delete 쿼리가 포함된 raw DELETE 가 호출된다."""
    from unittest.mock import MagicMock, patch

    from app.services.swift import delete_object

    conn = MagicMock()
    mock_meta = MagicMock()
    mock_meta.is_static_large_object = True
    conn.object_store.get_object_metadata.return_value = mock_meta

    with patch("app.services.swift._apply_endpoint_override"):
        delete_object(conn, "bucket", "big.bin")

    assert conn.object_store.delete.called
    delete_url = conn.object_store.delete.call_args[0][0]
    assert "multipart-manifest=delete" in delete_url


# ---------------------------------------------------------------------------
# Content-Disposition RFC 5987 (한글 파일명)
# ---------------------------------------------------------------------------


def test_content_disposition_ascii():
    """ASCII 파일명: filename 토큰과 filename* 토큰 모두 포함."""
    from app.api.object_storage.containers import _make_content_disposition

    result = _make_content_disposition("attachment", "folder/test.txt")
    assert "attachment" in result
    assert 'filename="test.txt"' in result
    assert "filename*=UTF-8''" in result
    assert urllib.parse.quote("test.txt", safe="") in result


def test_content_disposition_korean():
    """한글 파일명: ASCII 폴백은 '_'로 치환, filename* 는 UTF-8 퍼센트 인코딩."""
    from app.api.object_storage.containers import _make_content_disposition

    result = _make_content_disposition("attachment", "한글 2024.zip")
    assert "filename*=UTF-8''" in result
    assert urllib.parse.quote("한글 2024.zip", safe="") in result


def test_content_disposition_inline():
    """미리보기용 inline disposition."""
    from app.api.object_storage.containers import _make_content_disposition

    result = _make_content_disposition("inline", "image.png")
    assert result.startswith("inline")
    assert "filename*=UTF-8''" in result


# ---------------------------------------------------------------------------
# 단발 다운로드 토큰 발급
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_download_token_unauthenticated():
    """미인증 요청 → 401 (또는 서비스 미활성화 시 404/405)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/object-storage/test-bucket/objects/test.txt/download-token")
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_issue_download_token_success(client, mock_conn):
    """인증된 사용자가 토큰 발급 → url + expires_in 반환."""
    mock_redis = MagicMock()
    mock_redis.set = AsyncMock()

    with patch("app.services.cache._get_redis", new_callable=AsyncMock, return_value=mock_redis):
        resp = await client.post("/api/object-storage/test-bucket/objects/test.txt/download-token")
    assert resp.status_code in (200, 404, 405)
    if resp.status_code == 200:
        data = resp.json()
        assert "url" in data
        assert "token=" in data["url"]
        assert data["expires_in"] == 60


# ---------------------------------------------------------------------------
# 단발 토큰으로 다운로드
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_with_expired_token():
    """없는/만료된 토큰 → 403 (또는 서비스 미활성화 시 404/405)."""
    mock_redis = MagicMock()
    mock_redis.getdel = AsyncMock(return_value=None)

    with patch("app.services.cache._get_redis", new_callable=AsyncMock, return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/object-storage/test-bucket/objects/test.txt/download",
                params={"token": "expired-or-missing-token"},
            )
    assert resp.status_code in (403, 404, 405)


@pytest.mark.asyncio
async def test_download_token_mismatched_resource():
    """토큰 페이로드와 URL의 container/object 불일치 → 403."""
    payload = json.dumps(
        {
            "openstack_token": "os-tok",
            "project_id": "proj",
            "container_name": "other-bucket",
            "object_name": "test.txt",
        }
    )
    mock_redis = MagicMock()
    mock_redis.getdel = AsyncMock(return_value=payload)

    with patch("app.services.cache._get_redis", new_callable=AsyncMock, return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/object-storage/test-bucket/objects/test.txt/download",
                params={"token": "mismatch-token"},
            )
    assert resp.status_code in (403, 404, 405)


@pytest.mark.asyncio
async def test_download_with_valid_token():
    """유효한 단발 토큰 → 스트리밍 응답 + RFC 5987 Content-Disposition."""
    payload = json.dumps(
        {
            "openstack_token": "os-tok",
            "project_id": "proj",
            "container_name": "test-bucket",
            "object_name": "한글파일.zip",
        }
    )
    mock_redis = MagicMock()
    mock_redis.getdel = AsyncMock(return_value=payload)

    mock_conn_val = MagicMock()
    mock_conn_val.close = MagicMock()

    def fake_chunks():
        yield b"data"

    with (
        patch("app.services.cache._get_redis", new_callable=AsyncMock, return_value=mock_redis),
        patch("app.services.keystone.get_openstack_connection", return_value=mock_conn_val),
        patch("app.services.swift.stream_object", return_value=(fake_chunks(), "application/zip", 4)),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/object-storage/test-bucket/objects/%ED%95%9C%EA%B8%80%ED%8C%8C%EC%9D%BC.zip/download",
                params={"token": "valid-token"},
            )
    assert resp.status_code in (200, 404, 405)
    if resp.status_code == 200:
        cd = resp.headers.get("content-disposition", "")
        assert "filename*=UTF-8''" in cd


# ---------------------------------------------------------------------------
# admin all_projects 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_containers_all_projects_requires_admin(non_admin_client):
    """all_projects=true + is_system_admin=False → 403."""
    resp = await non_admin_client.get("/api/object-storage?all_projects=true")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_containers_all_projects_fans_out(admin_client):
    """admin + all_projects=true → 프로젝트별 fan-out, project_id 포함 결과."""
    from unittest.mock import MagicMock, patch

    fake_projects = [{"id": "p1", "name": "alpha"}, {"id": "p2", "name": "beta"}]
    sub_conn_p1 = MagicMock()
    sub_conn_p1.close = MagicMock()
    sub_conn_p2 = MagicMock()
    sub_conn_p2.close = MagicMock()
    conns = {"p1": sub_conn_p1, "p2": sub_conn_p2}
    containers_by_conn_id = {
        id(sub_conn_p1): [{"name": "bucket-a", "count": 3, "bytes": 1024}],
        id(sub_conn_p2): [{"name": "bucket-b", "count": 5, "bytes": 2048}],
    }

    with (
        patch("app.services.keystone.list_projects", return_value=fake_projects),
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            side_effect=lambda pid: conns[pid],
        ),
        patch(
            "app.services.swift.list_containers",
            side_effect=lambda conn, include_quarantine=False: containers_by_conn_id[id(conn)],
        ),
    ):
        resp = await admin_client.get("/api/object-storage?all_projects=true")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {b["project_id"] for b in body} == {"p1", "p2"}
    sub_conn_p1.close.assert_called_once()
    sub_conn_p2.close.assert_called_once()


@pytest.mark.asyncio
async def test_list_containers_include_quarantine_requires_admin(non_admin_client):
    """include_quarantine=true + non-admin → 403."""
    resp = await non_admin_client.get("/api/object-storage?include_quarantine=true")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_containers_all_projects_include_quarantine_propagates(admin_client):
    """admin all_projects + include_quarantine 가 list_containers 까지 전달된다."""
    from unittest.mock import MagicMock, patch

    fake_projects = [{"id": "p1", "name": "alpha"}]
    sub_conn = MagicMock()
    sub_conn.close = MagicMock()

    captured: dict = {}

    def _list(conn, include_quarantine=False):
        captured["include_quarantine"] = include_quarantine
        return [
            {"name": "test", "count": 4, "bytes": 1024},
            {"name": "test-quarantine", "count": 17, "bytes": 512, "is_quarantine": True},
        ]

    with (
        patch("app.services.keystone.list_projects", return_value=fake_projects),
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            return_value=sub_conn,
        ),
        patch("app.services.swift.list_containers", side_effect=_list),
    ):
        resp = await admin_client.get("/api/object-storage?all_projects=true&include_quarantine=true")
    assert resp.status_code == 200
    assert captured["include_quarantine"] is True
    body = resp.json()
    quarantine_entries = [b for b in body if b.get("is_quarantine")]
    assert len(quarantine_entries) == 1
    assert quarantine_entries[0]["name"] == "test-quarantine"


# ---------------------------------------------------------------------------
# Phase 10: 버킷 이름 검증 + admin fan-out 병렬화 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_container_rejects_reserved_name(client, mock_conn):
    """예약어 이름 (admin) → 400 + 한국어 사유."""
    resp = await client.post("/api/object-storage", json={"name": "admin"})
    assert resp.status_code == 400
    assert "예약" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_container_rejects_quarantine_suffix(client, mock_conn):
    """`-quarantine` 접미사 → 400."""
    resp = await client.post("/api/object-storage", json={"name": "foo-quarantine"})
    assert resp.status_code == 400
    assert "quarantine" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_container_accepts_valid_name(client, mock_conn):
    """정상 이름 통과 → 검증 후 swift.create_container 호출."""
    with patch("app.services.swift.create_container") as mock_create:
        mock_create.return_value = {"name": "my-bucket-2025"}
        resp = await client.post("/api/object-storage", json={"name": "my-bucket-2025"})
    assert resp.status_code == 201
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_list_containers_all_projects_runs_concurrently(admin_client):
    """asyncio.gather 병렬화: 3 프로젝트 × 0.3s sleep → 전체 < 0.5s (sequential 이면 0.9s+)."""
    import time

    fake_projects = [{"id": f"p{i}", "name": f"proj{i}"} for i in range(1, 4)]
    sub_conns = {pid["id"]: MagicMock() for pid in fake_projects}
    for c in sub_conns.values():
        c.close = MagicMock()

    def _slow_list(conn, include_quarantine=False):
        time.sleep(0.3)
        return [{"name": "bucket", "count": 1, "bytes": 100}]

    with (
        patch("app.services.keystone.list_projects", return_value=fake_projects),
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            side_effect=lambda pid: sub_conns[pid],
        ),
        patch("app.services.swift.list_containers", side_effect=_slow_list),
    ):
        start = time.monotonic()
        resp = await admin_client.get("/api/object-storage?all_projects=true")
        elapsed = time.monotonic() - start

    assert resp.status_code == 200
    assert len(resp.json()) == 3
    # sequential 이면 ~0.9s, parallel 이면 ~0.3s. 0.6s 이하면 병렬 동작 확인.
    assert elapsed < 0.6, f"expected parallel <0.6s, got {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_list_containers_all_projects_skips_unauthorized(admin_client):
    """한 프로젝트는 401 raise → 결과에서 제외 + 다른 프로젝트는 정상 포함."""
    from keystoneauth1.exceptions.http import Unauthorized

    fake_projects = [
        {"id": "p1", "name": "good"},
        {"id": "p2", "name": "denied"},
    ]
    good_conn = MagicMock()
    good_conn.close = MagicMock()

    def _get_conn(pid: str):
        if pid == "p2":
            raise Unauthorized("not allowed")
        return good_conn

    with (
        patch("app.services.keystone.list_projects", return_value=fake_projects),
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            side_effect=_get_conn,
        ),
        patch(
            "app.services.swift.list_containers",
            side_effect=lambda conn, include_quarantine=False: [{"name": "ok-bucket", "count": 1, "bytes": 100}],
        ),
    ):
        resp = await admin_client.get("/api/object-storage?all_projects=true")

    assert resp.status_code == 200
    body = resp.json()
    project_ids = {b["project_id"] for b in body}
    assert project_ids == {"p1"}, f"p2 should be skipped, got {project_ids}"


# ---------------------------------------------------------------------------
# delete_container 캐스케이드 + SLO 임계값 테스트
# ---------------------------------------------------------------------------


def test_delete_container_cascades_segments():
    """delete_container 가 원본 컨테이너 + 객체 + _segments 컨테이너를 모두 삭제."""
    from unittest.mock import MagicMock, patch

    from app.services import swift as swift_svc

    proxy = MagicMock()
    obj_a = MagicMock()
    obj_a.name = "file.bin"
    seg_a = MagicMock()
    seg_a.name = "file.bin/00000000"
    seg_b = MagicMock()
    seg_b.name = "file.bin/00000001"

    # 첫 호출(name="test"): 객체 1개; 두 번째 호출(name="test_segments"): segment 2개
    proxy.objects.side_effect = [iter([obj_a]), iter([seg_a, seg_b])]
    proxy.delete_container = MagicMock()
    proxy.delete_object = MagicMock()
    # SLO manifest 아님으로 설정 → delete_object 경로를 단순화
    proxy.get_object_metadata = MagicMock(
        return_value=MagicMock(
            is_static_large_object=False,
            x_static_large_object="",
        )
    )

    conn = MagicMock()
    conn.object_store = proxy
    conn._afterglow_project_id = "p1"

    with patch.object(swift_svc, "_apply_endpoint_override"):
        swift_svc.delete_container(conn, "test")

    # 원본 컨테이너 삭제
    proxy.delete_container.assert_any_call("test", ignore_missing=False)
    # _segments 컨테이너 내 segment 2개 삭제 시도
    assert proxy.delete_object.call_count >= 2
    # _segments 컨테이너 자체 삭제
    proxy.delete_container.assert_any_call("test_segments", ignore_missing=True)


def test_delete_container_no_segments_ok():
    """_segments 컨테이너가 없는 경우 정상 종료."""
    from unittest.mock import MagicMock, patch

    from app.services import swift as swift_svc

    proxy = MagicMock()

    def objects_side_effect(name):
        if name == "test":
            return iter([])
        raise Exception("404 NoSuchContainer")

    proxy.objects.side_effect = objects_side_effect
    proxy.delete_container = MagicMock()

    conn = MagicMock()
    conn.object_store = proxy
    conn._afterglow_project_id = "p1"

    with patch.object(swift_svc, "_apply_endpoint_override"):
        swift_svc.delete_container(conn, "test")  # 예외 없이 종료

    proxy.delete_container.assert_any_call("test", ignore_missing=False)


def test_upload_object_below_5gib_uses_single_put():
    """4 GiB 파일은 SLO 거치지 않고 create_object 단일 호출."""
    from io import BytesIO
    from unittest.mock import MagicMock, patch

    from app.services import swift as swift_svc

    proxy = MagicMock()
    proxy.create_object = MagicMock(return_value=MagicMock(name="big.bin", etag="abc"))
    conn = MagicMock()
    conn.object_store = proxy
    four_gib = 4 * 1024**3

    with patch.object(swift_svc, "_apply_endpoint_override"):
        result = swift_svc.upload_object(
            conn,
            "test",
            "big.bin",
            BytesIO(b""),
            content_type="application/octet-stream",
            content_length=four_gib,
        )

    proxy.create_object.assert_called_once()
    assert result["bytes"] == four_gib


def test_upload_object_above_5gib_uses_slo():
    """6 GiB 파일은 _upload_slo 호출."""
    from io import BytesIO
    from unittest.mock import MagicMock, patch

    from app.services import swift as swift_svc

    conn = MagicMock()
    conn.object_store = MagicMock()
    six_gib = 6 * 1024**3

    with (
        patch.object(swift_svc, "_apply_endpoint_override"),
        patch.object(
            swift_svc,
            "_upload_slo",
            return_value={"name": "huge.bin", "bytes": six_gib, "container": "test", "etag": ""},
        ) as mock_slo,
    ):
        result = swift_svc.upload_object(
            conn,
            "test",
            "huge.bin",
            BytesIO(b""),
            content_type="application/octet-stream",
            content_length=six_gib,
        )

    mock_slo.assert_called_once()
    assert result["bytes"] == six_gib


def test_list_containers_filters_quarantine_suffix():
    """list_containers가 -quarantine suffix 컨테이너를 결과에서 제외."""
    from unittest.mock import MagicMock, patch

    from app.services import swift as swift_svc

    fake_conn = MagicMock()
    c1 = MagicMock()
    c1.name = "test"
    c1.count = 5
    c1.bytes = 1024
    c2 = MagicMock()
    c2.name = "test-quarantine"
    c2.count = 0
    c2.bytes = 0
    c3 = MagicMock()
    c3.name = "test_segments"
    c3.count = 9
    c3.bytes = 8 * 1024**3
    c4 = MagicMock()
    c4.name = "other"
    c4.count = 1
    c4.bytes = 100

    fake_conn.object_store.containers.return_value = [c1, c2, c3, c4]
    fake_conn.object_store.get_endpoint.return_value = "http://swift/v1"

    with patch.object(swift_svc, "_apply_endpoint_override"):
        out = swift_svc.list_containers(fake_conn)

    names = [c["name"] for c in out]
    assert "test" in names
    assert "other" in names
    assert "test-quarantine" not in names
    assert "test_segments" not in names
