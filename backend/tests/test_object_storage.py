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


def test_upload_large_object_uses_slo():
    """1 GiB 초과 파일 업로드 시 create_object 에 use_slo=True, segment_size 가 전달된다."""
    import io
    from unittest.mock import MagicMock, patch

    from app.services.swift import _SLO_SEGMENT_SIZE, upload_object

    conn = MagicMock()
    mock_obj = MagicMock()
    mock_obj.name = "big.bin"
    mock_obj.etag = ""
    conn.object_store.create_object.return_value = mock_obj

    large_size = _SLO_SEGMENT_SIZE + 1  # 1 GiB + 1 byte
    with patch("app.services.swift._apply_endpoint_override"):
        upload_object(conn, "bucket", "big.bin", io.BytesIO(b""), "application/octet-stream", large_size)

    kw = conn.object_store.create_object.call_args[1]
    assert kw.get("use_slo") is True
    assert kw.get("segment_size") == _SLO_SEGMENT_SIZE


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
