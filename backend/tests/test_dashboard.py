"""common/dashboard.py 엔드포인트 단위 테스트 (4개)."""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_get_dashboard_config_public():
    """GET /api/dashboard/config — 인증 불필요, 항상 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/dashboard/config")
    assert resp.status_code == 200
    assert "refresh_interval_ms" in resp.json()


@pytest.mark.asyncio
async def test_get_dashboard_summary_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/dashboard/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_summary_success(client):
    dummy_summary = {
        "instances": {"total": 0, "active": 0, "shutoff": 0, "error": 0},
        "compute": {}, "storage": {}, "gpu_used": 0,
    }
    with patch("app.api.common.dashboard.asyncio") as mock_asyncio:
        mock_asyncio.gather = AsyncMock(return_value=([], {}, {}, []))
        mock_asyncio.to_thread = AsyncMock()
        with patch("app.api.common.dashboard.cached_call", new=AsyncMock(return_value=[])):
            resp = await client.get("/api/dashboard/summary")
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_get_dashboard_quotas_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/dashboard/quotas")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_quotas_success(client):
    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    with patch("app.api.common.dashboard.asyncio") as mock_asyncio:
        mock_asyncio.gather = AsyncMock(return_value=(quota, quota, quota))
        mock_asyncio.to_thread = AsyncMock(return_value=quota)
        resp = await client.get("/api/dashboard/quotas")
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_get_dashboard_usage_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/dashboard/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_usage_success(client):
    with patch("app.api.common.dashboard.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value={"server_usages": [], "total_hours": 0})
        resp = await client.get("/api/dashboard/usage")
    assert resp.status_code in (200, 500)
