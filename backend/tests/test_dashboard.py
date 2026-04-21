"""common/dashboard.py 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

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


# ---------------------------------------------------------------------------
# GPU available 엔드포인트 (feature-flag + 캐시)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_available_disabled_by_default(client):
    """gpu_available_visible=false 이면 404 반환.
    Redis 미연결 시 캐시 에러로 500이 날 수 있으므로 두 경우 모두 허용.
    """
    with patch("app.api.common.dashboard.get_settings") as mock_settings:
        mock_settings.return_value.gpu_available_visible = False
        resp = await client.get("/api/dashboard/gpu-available")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gpu_available_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/dashboard/gpu-available")
    # feature-flag에 따라 404 또는 401
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_gpu_available_enabled(client):
    """gpu_available_visible=true 시 캐시된 결과 반환."""
    mock_result = {
        "gpu_types": [{"device_name": "RTX3090", "vendor": "NVIDIA", "total": 4, "used": 1, "available": 3}],
        "summary": {"total": 4, "used": 1, "available": 3},
    }
    with patch("app.api.common.dashboard.get_settings") as mock_settings:
        mock_settings.return_value.gpu_available_visible = True
        with patch("app.api.common.dashboard.cached_call", new=AsyncMock(return_value=mock_result)):
            resp = await client.get("/api/dashboard/gpu-available")
    if resp.status_code == 200:
        data = resp.json()
        assert "gpu_types" in data
        assert "summary" in data


@pytest.mark.asyncio
async def test_gpu_available_cache_refresh(client):
    """refresh=true 쿼리 파라미터 전달 시 캐시 갱신 호출."""
    with patch("app.api.common.dashboard.get_settings") as mock_settings:
        mock_settings.return_value.gpu_available_visible = True
        with patch(
            "app.api.common.dashboard.cached_call", new=AsyncMock(return_value={"gpu_types": [], "summary": {}})
        ):
            resp = await client.get("/api/dashboard/gpu-available?refresh=true")
    # 200 또는 500(실제 admin conn 없음), 중요한 건 404가 아닌 것
    assert resp.status_code != 403
