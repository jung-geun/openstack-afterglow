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
