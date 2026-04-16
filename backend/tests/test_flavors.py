"""compute/flavors.py 엔드포인트 단위 테스트 (1개)."""
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_list_flavors_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/flavors")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_flavors_success(client, mock_conn):
    with patch("app.api.compute.flavors.nova") as mock_nova:
        mock_nova.list_flavors.return_value = []
        resp = await client.get("/api/flavors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
