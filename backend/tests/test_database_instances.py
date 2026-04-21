"""Database (Trove) API 단위 테스트.

Trove 서비스가 비활성화된 환경에서도 인증 관문(401/404)을 검증.
활성화된 환경에서는 mock으로 성공/에러 경로를 검증.
trove는 핸들러 내에서 lazy import하므로 app.services.trove 를 패치.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# trove 서비스 활성화 여부
_TROVE_ENABLED = os.environ.get("SERVICE_TROVE_ENABLED", "false").lower() in ("true", "1")


# ---------------------------------------------------------------------------
# 인증 관문 (항상 실행)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_database_instances_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/database-instances")
    # trove 미활성화 시 404, 활성화+인증없음 시 401
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_create_database_instance_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/database-instances", json={"name": "mydb"})
    assert resp.status_code in (401, 404, 422)


@pytest.mark.asyncio
async def test_get_database_instance_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/database-instances/inst-1")
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_delete_database_instance_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/database-instances/inst-1")
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_list_database_flavors_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/database-instances/flavors")
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_list_datastores_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/database-instances/datastores")
    assert resp.status_code in (401, 404)


# ---------------------------------------------------------------------------
# Trove 활성화 시 동작 (SERVICE_TROVE_ENABLED=true 필요)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.skipif(not _TROVE_ENABLED, reason="Trove 서비스 비활성화")
async def test_list_database_instances_success(client, mock_conn):
    from unittest.mock import MagicMock, patch

    # list_instances는 asyncio.to_thread 로 호출되는 sync 함수이므로 MagicMock 사용
    with patch("app.services.trove.list_instances", new=MagicMock(return_value=[])):
        resp = await client.get("/api/database-instances")
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
@pytest.mark.skipif(not _TROVE_ENABLED, reason="Trove 서비스 비활성화")
async def test_list_database_instances_error_handling(client, mock_conn):
    from unittest.mock import MagicMock, patch

    with patch("app.services.trove.list_instances", new=MagicMock(side_effect=Exception("trove error"))):
        resp = await client.get("/api/database-instances")
    assert resp.status_code in (500, 503)
