"""Phase 52b — /api/dashboard/usage-report forecast 구조 검증."""

from unittest.mock import AsyncMock, patch

import pytest


def _patch_redis():
    from app.services import cache as cache_mod

    fake = AsyncMock()
    fake.get.return_value = None
    fake.setex.return_value = None
    fake.delete.return_value = None
    return patch.object(cache_mod, "_get_client", return_value=fake)


@pytest.mark.asyncio
async def test_usage_report_forecast_structure(client, mock_conn):
    """forecast.vcpu_pct / memory_pct / storage_pct 필드 존재 + 0~100 범위."""
    with (
        _patch_redis(),
        patch("app.api.common.dashboard.nova.get_project_usage", return_value={
            "total_hours": 100.0,
            "total_vcpu_hours": 200.0,
            "server_usages": [],
        }),
        patch("app.api.common.dashboard.nova.get_project_quota", return_value={
            "cores": {"in_use": 4, "limit": 20},
            "ram": {"in_use": 8192, "limit": 51200},
            "gigabytes": {"in_use": 100, "limit": 1000},
        }),
    ):
        resp = await client.get("/api/dashboard/usage-report?range=30d")

    assert resp.status_code == 200
    data = resp.json()
    forecast = data["forecast"]
    assert "vcpu_pct" in forecast
    assert "memory_pct" in forecast
    assert "storage_pct" in forecast
    assert 0 <= forecast["vcpu_pct"] <= 100
    assert 0 <= forecast["memory_pct"] <= 100
    assert 0 <= forecast["storage_pct"] <= 100
    # 4/20 = 20%
    assert forecast["vcpu_pct"] == 20.0


@pytest.mark.asyncio
async def test_usage_report_forecast_vcpu_pct_matches_quota(client, mock_conn):
    """vcpu_pct = vcpus_in_use / vcpus_limit * 100."""
    with (
        _patch_redis(),
        patch("app.api.common.dashboard.nova.get_project_usage", return_value={}),
        patch("app.api.common.dashboard.nova.get_project_quota", return_value={
            "cores": {"in_use": 10, "limit": 20},
        }),
    ):
        resp = await client.get("/api/dashboard/usage-report")

    assert resp.status_code == 200
    assert resp.json()["forecast"]["vcpu_pct"] == 50.0


@pytest.mark.asyncio
async def test_usage_report_forecast_zero_when_no_limit(client, mock_conn):
    """limit=0 시 ZeroDivisionError 없이 0.0 반환."""
    with (
        _patch_redis(),
        patch("app.api.common.dashboard.nova.get_project_usage", return_value={}),
        patch("app.api.common.dashboard.nova.get_project_quota", return_value={}),
    ):
        resp = await client.get("/api/dashboard/usage-report")

    assert resp.status_code == 200
    forecast = resp.json()["forecast"]
    assert forecast["vcpu_pct"] == 0.0
    assert forecast["memory_pct"] == 0.0
    assert forecast["storage_pct"] == 0.0


@pytest.mark.asyncio
async def test_usage_report_quota_still_present(client, mock_conn):
    """기존 quota 필드(vcpus_in_use, vcpus_limit)는 호환성을 위해 유지."""
    with (
        _patch_redis(),
        patch("app.api.common.dashboard.nova.get_project_usage", return_value={}),
        patch("app.api.common.dashboard.nova.get_project_quota", return_value={
            "cores": {"in_use": 5, "limit": 20},
        }),
    ):
        resp = await client.get("/api/dashboard/usage-report")

    assert resp.status_code == 200
    data = resp.json()
    assert "quota" in data
    assert data["quota"]["vcpus_in_use"] == 5
    assert data["quota"]["vcpus_limit"] == 20
