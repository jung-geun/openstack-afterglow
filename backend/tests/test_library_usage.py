"""라이브러리 사용 통계 시계열 엔드포인트 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_library_usage_timeseries_unauthenticated():
    """인증 없이 library_usage timeseries 조회 시 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/admin/timeseries/library_usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_library_usage_timeseries_non_admin_forbidden(client):
    """일반 사용자가 library_usage 조회 시 403."""
    resp = await client.get("/api/admin/timeseries/library_usage")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_library_usage_timeseries_success(admin_client):
    """관리자가 library_usage 조회 시 200 + 리스트 반환."""
    sample_data = [
        {"ts": 1_700_000_000.0, "lib:python311": 3, "lib:torch": 2},
        {"ts": 1_700_001_000.0, "lib:python311": 4, "lib:torch": 3},
    ]
    with patch("app.services.timeseries.get_timeseries", AsyncMock(return_value=sample_data)):
        resp = await admin_client.get("/api/admin/timeseries/library_usage?range=1d")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["lib:python311"] == 3


@pytest.mark.asyncio
async def test_library_usage_timeseries_empty(admin_client):
    """스냅샷 없을 때 빈 리스트 반환."""
    with patch("app.services.timeseries.get_timeseries", AsyncMock(return_value=[])):
        resp = await admin_client.get("/api/admin/timeseries/library_usage?range=7d")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_library_usage_invalid_range(admin_client):
    """잘못된 range 파라미터는 422 반환."""
    resp = await admin_client.get("/api/admin/timeseries/library_usage?range=100d")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_resource_type_returns_400(admin_client):
    """unknown resource_type은 400 반환."""
    with patch("app.services.timeseries.get_timeseries", AsyncMock(return_value=[])):
        resp = await admin_client.get("/api/admin/timeseries/nonexistent?range=7d")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_library_usage_known_resource_types_accepted(admin_client):
    """기존 resource_type(instances, volumes, file_storage, networks)도 여전히 200."""
    with patch("app.services.timeseries.get_timeseries", AsyncMock(return_value=[])):
        for rt in ("instances", "volumes", "file_storage", "networks", "library_usage"):
            resp = await admin_client.get(f"/api/admin/timeseries/{rt}?range=7d")
            assert resp.status_code == 200, f"{rt} returned {resp.status_code}"
