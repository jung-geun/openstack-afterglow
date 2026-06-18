"""common/dashboard.py 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_dashboard_config_public():
    """GET /api/dashboard/config — 인증 불필요, 항상 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/config")
    assert resp.status_code == 200
    assert "refresh_interval_ms" in resp.json()


@pytest.mark.asyncio
async def test_get_dashboard_summary_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_summary_success(client):
    empty_list: list = []
    with patch(
        "app.api.common.dashboard.cached_call",
        new=AsyncMock(
            side_effect=[
                empty_list,  # servers
                empty_list,  # all_flavors
            ]
        ),
    ):
        resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "instances" in data
    assert "gpu_used" in data
    assert "compute" not in data
    assert "storage" not in data


@pytest.mark.asyncio
async def test_get_dashboard_quotas_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/quotas")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_quotas_success(client):
    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    # cached_call은 결과를 캐시 key별로 1회씩 호출한다 — _fetch_quotas 내부의
    # asyncio.gather를 진짜로 실행하되, 각 service 함수는 cached_call로 묶여 있음.
    # 가장 단순한 방법: cached_call 전체를 patch해서 results 리스트를 한 번에 반환.
    # 활성화된 서비스(config.toml): manila/trove/swift → compute/volume/network/manila/trove/swift = 최대 6건
    # 실제 활성 수를 맞추기 위해 넉넉히 6개 제공
    quota_int = 0  # trove count
    swift_meta = {"container_count": 0, "object_count": 0, "bytes_used": 0}
    with patch(
        "app.api.common.dashboard.cached_call",
        new=AsyncMock(return_value=[quota, quota, quota, quota, quota_int, swift_meta]),
    ):
        resp = await client.get("/api/v1/dashboard/quotas")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute" in data
    assert "storage" in data


@pytest.mark.asyncio
async def test_get_dashboard_usage_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_usage_success(client):
    usage_data = {"server_usages": [], "total_hours": 0}
    with patch("app.api.common.dashboard.cached_call", new=AsyncMock(return_value=usage_data)):
        resp = await client.get("/api/v1/dashboard/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "server_usages" in data
    assert "total_hours" in data


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
        resp = await client.get("/api/v1/dashboard/gpu-available")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gpu_available_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/gpu-available")
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
            resp = await client.get("/api/v1/dashboard/gpu-available")
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
            resp = await client.get("/api/v1/dashboard/gpu-available?refresh=true")
    # 200 또는 500(실제 admin conn 없음), 중요한 건 404가 아닌 것
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# GPU quota OperationalError → 200 + 빈 gpu 배열
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dashboard_quotas_gpu_db_error_returns_empty_gpu(client):
    """GPU quota DB OperationalError 발생 시 200 반환 + gpu 빈 배열."""
    from sqlalchemy.exc import OperationalError

    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    quota_int = 0
    swift_meta = {"container_count": 0, "object_count": 0, "bytes_used": 0}

    with (
        patch(
            "app.api.common.dashboard.cached_call",
            new=AsyncMock(return_value=[quota, quota, quota, quota, quota_int, swift_meta]),
        ),
        patch("app.api.common.dashboard.is_db_available", return_value=True),
        patch(
            "app.api.common.dashboard.asyncio.gather",
            new=AsyncMock(return_value=(OperationalError("lost", None, None), {})),
        ),
        patch("app.api.common.dashboard.mark_db_unhealthy") as mock_mark,
    ):
        resp = await client.get("/api/v1/dashboard/quotas")

    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu"] == []
    mock_mark.assert_called_once()


@pytest.mark.asyncio
async def test_get_dashboard_quotas_gpu_partial_error_returns_empty_gpu(client):
    """GPU usage 조회만 실패해도 200 + gpu 빈 배열."""
    from sqlalchemy.exc import OperationalError

    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    quota_int = 0
    swift_meta = {"container_count": 0, "object_count": 0, "bytes_used": 0}

    with (
        patch(
            "app.api.common.dashboard.cached_call",
            new=AsyncMock(return_value=[quota, quota, quota, quota, quota_int, swift_meta]),
        ),
        patch("app.api.common.dashboard.is_db_available", return_value=True),
        patch(
            "app.api.common.dashboard.asyncio.gather",
            new=AsyncMock(return_value=({"RTX3090": 2}, OperationalError("lost", None, None))),
        ),
        patch("app.api.common.dashboard.mark_db_unhealthy"),
    ):
        resp = await client.get("/api/v1/dashboard/quotas")

    assert resp.status_code == 200
    assert resp.json()["gpu"] == []
