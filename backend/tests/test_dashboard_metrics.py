"""Phase 52e — /api/dashboard/metrics/trend PromQL trend endpoint 검증."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_trend_returns_structure(client, mock_conn):
    """prometheus_available + vcpu/memory/storage 시계열 구조 반환."""
    fake_series = [{"ts": 1000, "value": 25.0}, {"ts": 1086400, "value": 30.0}]

    with patch("app.api.common.dashboard.prom_query.query_range", new_callable=AsyncMock) as mock_qr:
        mock_qr.return_value = fake_series
        resp = await client.get("/api/dashboard/metrics/trend")

    assert resp.status_code == 200
    data = resp.json()
    assert "prometheus_available" in data
    assert "vcpu" in data
    assert "memory" in data
    assert "storage" in data
    assert isinstance(data["vcpu"]["data"], list)
    assert data["vcpu"]["points"] == 2
    assert data["vcpu"]["available"] is True
    assert data["prometheus_available"] is True


@pytest.mark.asyncio
async def test_trend_prometheus_unavailable_returns_empty(client, mock_conn):
    """Prometheus 미설치 시 prometheus_available=False + data=[] + 500 미발생."""
    from app.services.prom_query import PromUnavailable

    with patch("app.api.common.dashboard.prom_query.query_range", new_callable=AsyncMock) as mock_qr:
        mock_qr.side_effect = PromUnavailable("연결 실패")
        resp = await client.get("/api/dashboard/metrics/trend")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prometheus_available"] is False
    assert data["vcpu"]["data"] == []
    assert data["vcpu"]["available"] is False


@pytest.mark.asyncio
async def test_trend_partial_failure_returns_available_series(client, mock_conn):
    """일부 쿼리만 성공 시 성공한 시계열만 data 포함."""
    from app.services.prom_query import PromUnavailable

    fake_vcpu = [{"ts": 1000, "value": 10.0}]

    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fake_vcpu
        raise PromUnavailable("no data")

    with patch("app.api.common.dashboard.prom_query.query_range", side_effect=_side_effect):
        resp = await client.get("/api/dashboard/metrics/trend")

    assert resp.status_code == 200
    data = resp.json()
    assert data["vcpu"]["available"] is True
    assert data["memory"]["available"] is False
    # 하나라도 성공하면 prometheus_available=True
    assert data["prometheus_available"] is True


@pytest.mark.asyncio
async def test_trend_data_values_rounded(client, mock_conn):
    """반환 데이터 값이 소수점 2자리로 반올림됨."""
    fake_series = [{"ts": 1000, "value": 25.12345}]

    with patch("app.api.common.dashboard.prom_query.query_range", new_callable=AsyncMock) as mock_qr:
        mock_qr.return_value = fake_series
        resp = await client.get("/api/dashboard/metrics/trend")

    assert resp.status_code == 200
    assert resp.json()["vcpu"]["data"][0] == 25.12
