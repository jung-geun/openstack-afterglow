"""common/libraries.py 엔드포인트 단위 테스트 (2개)."""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_list_libraries_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/libraries")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_libraries_success(client, mock_conn):
    with patch("app.api.common.libraries.lib_svc") as mock_lib, \
         patch("app.api.common.libraries.manila") as mock_manila:
        mock_lib.get_all.return_value = []
        mock_manila.list_file_storages.return_value = []
        resp = await client.get("/api/libraries")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_prebuilt_file_storages_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/libraries/file-storages")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_prebuilt_file_storages_success(client, mock_conn):
    with patch("app.api.common.libraries.manila") as mock_manila:
        mock_manila.list_file_storages.return_value = []
        resp = await client.get("/api/libraries/file-storages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
