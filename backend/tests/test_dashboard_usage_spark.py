"""Phase 53g — /api/dashboard/metrics/trend 전체 검증.

범위: range=24h|7d|14d, network 필드 분리, storage=node_filesystem,
NaN 필터, Redis 캐시, invalid range 400.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _default_servers(mock_conn):
    """대시보드 PromQL 핸들러는 UUID 필터 구성을 위해 서버 1개 이상이 필요하다.
    빈 프로젝트 테스트는 mock_conn.compute.servers.return_value = [] 로 덮어쓴다."""
    s = MagicMock()
    s.id = "test-server-uuid-1"
    mock_conn.compute.servers.return_value = [s]


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
# range=14d
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_14d_structure(client, mock_conn):
    """range=14d 시 vcpu/memory/storage/network/range 키 반환."""
    with _patch_prom_query([{"ts": 1000, "value": 10.0}] * 14):
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=14d")

    assert resp.status_code == 200
    data = resp.json()
    for key in ("vcpu", "memory", "storage", "network", "prometheus_available", "range"):
        assert key in data, f"응답에 '{key}' 키 누락"
    assert data["prometheus_available"] is True
    assert data["vcpu"]["points"] == 14
    assert data["range"] == "14d"
    assert "unit" in data["network"]
    assert data["network"]["unit"] == "KiB/s"


@pytest.mark.asyncio
async def test_trend_default_is_14d(client, mock_conn):
    """range 파라미터 생략 시 14d와 동일 동작."""
    with _patch_prom_query([]):
        resp_default = await client.get("/api/v1/dashboard/metrics/trend")
        resp_14d = await client.get("/api/v1/dashboard/metrics/trend?range=14d")

    assert resp_default.status_code == 200
    assert resp_14d.status_code == 200
    assert resp_default.json()["prometheus_available"] == resp_14d.json()["prometheus_available"]
    assert resp_default.json()["range"] == "14d"


@pytest.mark.asyncio
async def test_trend_14d_prometheus_unavailable_fallback(client, mock_conn):
    """14d도 Prometheus 미설치 시 graceful fallback."""
    with _patch_prom_unavailable():
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=14d")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prometheus_available"] is False
    assert data["vcpu"]["available"] is False


# ---------------------------------------------------------------------------
# range=24h
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_24h_structure(client, mock_conn):
    """range=24h 시 응답 구조 정상 + prometheus_available=True."""
    sample = [{"ts": i * 300, "value": float(i)} for i in range(288)]
    with _patch_prom_query(sample):
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=24h")

    assert resp.status_code == 200
    data = resp.json()
    for key in ("vcpu", "memory", "storage", "network", "prometheus_available", "range"):
        assert key in data
    assert data["prometheus_available"] is True
    assert data["vcpu"]["points"] == 288
    assert data["range"] == "24h"


@pytest.mark.asyncio
async def test_trend_24h_prometheus_unavailable_fallback(client, mock_conn):
    """Prometheus 미설치 시 500 없이 prometheus_available=False + 빈 배열 반환."""
    with _patch_prom_unavailable():
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=24h")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prometheus_available"] is False
    assert data["vcpu"]["data"] == []
    assert data["memory"]["data"] == []
    assert data["storage"]["data"] == []
    assert data["network"]["data"] == []


@pytest.mark.asyncio
async def test_trend_range_24h_returns_network_field(client, mock_conn):
    """network 필드가 별도로 존재하며 storage와 분리되어 있다."""
    net_sample = [{"ts": i * 300, "value": float(i * 10)} for i in range(10)]
    with _patch_prom_query(net_sample):
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=24h")

    data = resp.json()
    assert "network" in data
    assert "storage" in data
    # storage와 network는 같은 값이어도 다른 키 — 분리 확인
    assert data["network"]["unit"] == "KiB/s"
    assert "unit" not in data["storage"]


# ---------------------------------------------------------------------------
# range=7d
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_range_7d_structure(client, mock_conn):
    """range=7d 응답에 range='7d' 반환."""
    with _patch_prom_query([{"ts": 1000, "value": 50.0}] * 5):
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=7d")

    assert resp.status_code == 200
    assert resp.json()["range"] == "7d"


@pytest.mark.asyncio
async def test_trend_range_7d_step_3600(client, mock_conn):
    """range=7d 시 prom_query.query_range에 step_s=3600이 전달된다."""
    with _patch_prom_query([]) as mock_qr:
        await client.get("/api/v1/dashboard/metrics/trend?range=7d")

    for c in mock_qr.call_args_list:
        assert c.kwargs.get("step_s") == 3600, f"step_s 불일치: {c.kwargs}"


# ---------------------------------------------------------------------------
# vCPU/RAM PromQL 식 검증 (node_exporter 기반, libvirt 미사용 확인)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_vcpu_uses_libvirt_cpu_expr(client, mock_conn):
    """vCPU PromQL 식에 libvirt_domain_info_cpu_time + libvirt_domain_openstack_info 조인이 포함된다."""
    captured_exprs: list[str] = []

    async def _capture(expr, *, start_ts, end_ts, step_s):
        captured_exprs.append(expr)
        return []

    with patch("app.api.common.dashboard.prom_query.query_range", side_effect=_capture):
        await client.get("/api/v1/dashboard/metrics/trend?range=24h")

    cpu_exprs = [e for e in captured_exprs if "libvirt_domain_info_cpu_time_seconds_total" in e]
    assert cpu_exprs, "libvirt_domain_info_cpu_time_seconds_total 식이 쿼리에 없음"
    assert any("libvirt_domain_openstack_info" in e for e in cpu_exprs), "libvirt_domain_openstack_info 조인이 없음"
    assert any('project_id="' in e for e in cpu_exprs), "project_id tenant filter가 없음"
    assert any("on (instance, domain)" in e for e in cpu_exprs), "instance/domain 조인이 없음"
    node_cpu = [e for e in captured_exprs if "node_cpu_seconds_total" in e]
    assert not node_cpu, "node_cpu_seconds_total이 여전히 쿼리에 남아 있음"


@pytest.mark.asyncio
async def test_trend_memory_uses_libvirt_memory_expr(client, mock_conn):
    """RAM PromQL 식에 libvirt_domain_memory_stats_used_percent + openstack_info 조인이 포함된다."""
    captured_exprs: list[str] = []

    async def _capture(expr, *, start_ts, end_ts, step_s):
        captured_exprs.append(expr)
        return []

    with patch("app.api.common.dashboard.prom_query.query_range", side_effect=_capture):
        await client.get("/api/v1/dashboard/metrics/trend?range=24h")

    mem_exprs = [e for e in captured_exprs if "libvirt_domain_memory_stats_used_percent" in e]
    assert mem_exprs, "libvirt_domain_memory_stats_used_percent 식이 쿼리에 없음"
    assert any("libvirt_domain_openstack_info" in e for e in mem_exprs), "libvirt_domain_openstack_info 조인이 없음"
    node_mem = [e for e in captured_exprs if "node_memory_MemAvailable_bytes" in e]
    assert not node_mem, "node_memory_MemAvailable_bytes가 여전히 쿼리에 남아 있음"


# ---------------------------------------------------------------------------
# 프로젝트 인스턴스 열거 없이 PromQL은 빈 데이터도 reachability를 판정한다.
#
@pytest.mark.asyncio
async def test_trend_empty_project_queries_project_scope(client, mock_conn):
    """Nova 열거 없이 세 개의 project-scoped PromQL 쿼리를 실행한다."""
    mock_conn.compute.servers.return_value = []
    with _patch_prom_query([]) as mock_qr:
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=24h&include_network=false")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prometheus_available"] is True
    assert data["vcpu"]["available"] is False
    assert data["network"] == {"data": [], "points": 0, "available": False, "unit": "KiB/s"}
    assert mock_qr.call_count == 3, f"include_network=false는 세 쿼리만 실행, 실제: {mock_qr.call_count}"
    mock_conn.compute.servers.assert_not_called()


# ---------------------------------------------------------------------------
# Storage PromQL 식 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_storage_uses_node_filesystem_expr(client, mock_conn):
    """storage PromQL 식에 node_filesystem이 포함되고 cinder_volume_capacity_bytes가 없다."""
    captured_exprs: list[str] = []

    async def _capture(expr, *, start_ts, end_ts, step_s):
        captured_exprs.append(expr)
        return []

    with patch("app.api.common.dashboard.prom_query.query_range", side_effect=_capture):
        await client.get("/api/v1/dashboard/metrics/trend?range=14d")

    storage_exprs = [e for e in captured_exprs if "node_filesystem" in e]
    assert storage_exprs, "node_filesystem 식이 쿼리에 없음"
    cinder_exprs = [e for e in captured_exprs if "cinder_volume_capacity_bytes" in e]
    assert not cinder_exprs, "cinder_volume_capacity_bytes가 여전히 쿼리에 남아 있음"


# ---------------------------------------------------------------------------
# Invalid range → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_invalid_range_returns_400(client, mock_conn):
    """허용되지 않는 range 값은 400 반환."""
    with _patch_prom_query([]):
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=30d")
    assert resp.status_code == 400

    with _patch_prom_query([]):
        resp2 = await client.get("/api/v1/dashboard/metrics/trend?range=1h")
    assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# NaN 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_nan_values_filtered(client, mock_conn):
    """NaN 포인트는 제거되며 Prometheus 자체는 reachable로 판정된다."""
    nan_series = [{"ts": 1000, "value": float("nan")}]
    with _patch_prom_query(nan_series):
        resp = await client.get("/api/v1/dashboard/metrics/trend?range=24h")

    data = resp.json()
    assert data["vcpu"]["data"] == []
    assert data["vcpu"]["available"] is False
    assert data["prometheus_available"] is True


# ---------------------------------------------------------------------------
# Redis 캐시 — 연속 호출 시 prom_query 한 번만 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trend_14d_uses_redis_cache(client, mock_conn):
    """동일 (project_id, range) 연속 호출 시 캐시 히트 → prom_query 중복 호출 없음."""
    from app.services.cache import set_backend

    class _DictBackend:
        def __init__(self):
            self._data: dict[str, str] = {}

        async def get(self, key: str):
            return self._data.get(key)

        async def set(self, key: str, value, ttl: int):
            self._data[key] = value if isinstance(value, str) else json.dumps(value)

        async def delete(self, *keys: str):
            for k in keys:
                self._data.pop(k, None)

    dummy = _DictBackend()
    set_backend(dummy)
    try:
        sample = [{"ts": i * 21600, "value": 50.0} for i in range(56)]
        with _patch_prom_query(sample) as mock_qr:
            # 캐시 기본 OFF — read-through 를 쓰려면 ?cache=true 로 opt-in
            await client.get("/api/v1/dashboard/metrics/trend?range=14d&cache=true")
            await client.get("/api/v1/dashboard/metrics/trend?range=14d&cache=true")

        # 4개 식(vcpu, memory, storage, network) × 1회 = 4 (두 번째 호출은 캐시 히트)
        assert mock_qr.call_count == 4, f"캐시가 작동하면 4번 호출 기대, 실제: {mock_qr.call_count}"
    finally:
        set_backend(None)
