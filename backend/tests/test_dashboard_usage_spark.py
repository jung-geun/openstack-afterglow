"""Phase 53c — /api/dashboard/metrics/trend range 파라미터 + 24h flavor-relative 검증."""

from unittest.mock import AsyncMock, patch

import pytest


def _patch_prom_query(return_value=None):
    """prom_query.query_range를 mock — 기본값: 빈 series."""
    if return_value is None:
        return_value = []
    return patch(
        "app.api.common.dashboard.prom_query.query_range",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _patch_prom_unavailable():
    """Prometheus 미설치 환경 시뮬레이션 — PromUnavailable 예외."""
    from app.services.prom_query import PromUnavailable
    return patch(
        "app.api.common.dashboard.prom_query.query_range",
        side_effect=PromUnavailable("Prometheus not configured"),
    )


# ---------------------------------------------------------------------------
# range=14d (기존 동작 — 호환성)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trend_14d_structure(client, mock_conn):
    """range=14d 시 vcpu/memory/storage 3개 키 반환."""
    with _patch_prom_query([{"ts": 1000, "value": 10.0}] * 14):
        resp = await client.get("/api/dashboard/metrics/trend?range=14d")

    assert resp.status_code == 200
    data = resp.json()
    for key in ("vcpu", "memory", "storage", "prometheus_available"):
        assert key in data
    assert data["prometheus_available"] is True
    assert data["vcpu"]["points"] == 14


@pytest.mark.asyncio
async def test_trend_default_is_14d(client, mock_conn):
    """range 파라미터 생략 시 14d와 동일 동작."""
    with _patch_prom_query([]):
        resp_default = await client.get("/api/dashboard/metrics/trend")
        resp_14d = await client.get("/api/dashboard/metrics/trend?range=14d")

    assert resp_default.status_code == 200
    assert resp_14d.status_code == 200
    assert resp_default.json()["prometheus_available"] == resp_14d.json()["prometheus_available"]


# ---------------------------------------------------------------------------
# range=24h (신규 — flavor-relative)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trend_24h_structure(client, mock_conn):
    """range=24h 시 응답 구조 동일 + prometheus_available=True."""
    sample = [{"ts": i * 300, "value": float(i)} for i in range(288)]
    with _patch_prom_query(sample):
        resp = await client.get("/api/dashboard/metrics/trend?range=24h")

    assert resp.status_code == 200
    data = resp.json()
    assert "vcpu" in data
    assert "memory" in data
    assert "storage" in data
    assert data["prometheus_available"] is True
    assert data["vcpu"]["points"] == 288


@pytest.mark.asyncio
async def test_trend_24h_prometheus_unavailable_fallback(client, mock_conn):
    """Prometheus 미설치 시 500 없이 prometheus_available=False + 빈 배열 반환."""
    with _patch_prom_unavailable():
        resp = await client.get("/api/dashboard/metrics/trend?range=24h")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prometheus_available"] is False
    assert data["vcpu"]["data"] == []
    assert data["memory"]["data"] == []
    assert data["storage"]["data"] == []


@pytest.mark.asyncio
async def test_trend_14d_prometheus_unavailable_fallback(client, mock_conn):
    """14d도 Prometheus 미설치 시 graceful fallback."""
    with _patch_prom_unavailable():
        resp = await client.get("/api/dashboard/metrics/trend?range=14d")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prometheus_available"] is False
    assert data["vcpu"]["available"] is False
