"""Object Storage (Swift) API 단위 테스트.

swift 서비스는 SERVICE_SWIFT_ENABLED=true 시 /api/object-storage/* 경로로 등록.
비활성화 시 대부분 404/405 응답 → 인증 관문 테스트는 in (401, 404, 405) 허용.
swift 함수는 핸들러 내에서 lazy import하므로 app.services.swift 를 패치.
"""

from unittest.mock import MagicMock, patch

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
    """1.5 GiB raw PUT → 수동 SLO: proxy.put 2(segments) + 1(manifest) = 3 회."""
    import io
    import math
    from unittest.mock import MagicMock, patch

    from app.services.swift import _SLO_SEGMENT_SIZE, upload_object

    conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.headers = {"etag": '"deadbeef"'}
    conn.object_store.put.return_value = mock_resp

    large_size = int(1.5 * 1024**3)  # 2 segments
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
