"""인스턴스별 Prometheus 메트릭 조회."""

from __future__ import annotations

import asyncio
import time
from typing import Literal, get_args

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_os_conn, get_token_info
from app.services import nova
from app.services.prom_query import PromBadQuery, PromUnavailable, calc_step, query_range

router = APIRouter()

_RANGE_SECONDS: dict[str, int] = {
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
}

MetricKey = Literal[
    "cpu",
    "memory",
    "network_rx",
    "network_tx",
    "disk_read",
    "disk_write",
    "gpu_util",
    "gpu_mem",
]

_VALID_METRICS: frozenset[str] = frozenset(get_args(MetricKey))
_GPU_METRICS: frozenset[str] = frozenset({"gpu_util", "gpu_mem"})


def _build_expr(metric: str, instance_id: str) -> str:
    # kolla-ansible OpenStack SD 가 부여한 라벨 — instance_id (UUID) 가 unique key.
    # job 필터를 두지 않아 internal/external 두 job 모두 커버한다.
    sel = f'instance_id="{instance_id}"'
    exclude_ifaces = r"lo|veth.*|docker.*|cni.*"
    if metric == "cpu":
        return f'100 - (avg by (instance_id) (rate(node_cpu_seconds_total{{{sel},mode="idle"}}[2m])) * 100)'
    if metric == "memory":
        return f"(1 - node_memory_MemAvailable_bytes{{{sel}}} / node_memory_MemTotal_bytes{{{sel}}}) * 100"
    if metric == "network_rx":
        return f'sum by (instance_id) (rate(node_network_receive_bytes_total{{{sel},device!~"{exclude_ifaces}"}}[2m]))'
    if metric == "network_tx":
        return f'sum by (instance_id) (rate(node_network_transmit_bytes_total{{{sel},device!~"{exclude_ifaces}"}}[2m]))'
    if metric == "disk_read":
        return f"sum by (instance_id) (rate(node_disk_read_bytes_total{{{sel}}}[2m]))"
    if metric == "disk_write":
        return f"sum by (instance_id) (rate(node_disk_written_bytes_total{{{sel}}}[2m]))"
    if metric == "gpu_util":
        return f"avg by (instance_id) (DCGM_FI_DEV_GPU_UTIL{{{sel}}})"
    if metric == "gpu_mem":
        return f"avg by (instance_id) (DCGM_FI_DEV_FB_USED{{{sel}}} / DCGM_FI_DEV_FB_TOTAL{{{sel}}}) * 100"
    raise ValueError(f"unknown metric: {metric}")


def _build_libvirt_expr(metric: str, instance_id: str) -> str | None:
    """libvirt-exporter 기반 폴백 PromQL. node_exporter 미노출 인스턴스(테넌트망 격리)용.

    domain 라벨(instance-XXXXXXXX) → libvirt_domain_openstack_info 조인 → instance_id(UUID).
    GPU 메트릭은 DCGM 전용이므로 None 반환.
    """
    iid = f'instance_id="{instance_id}"'
    join = f"* on (domain) group_left(instance_id) libvirt_domain_openstack_info{{{iid}}}"
    if metric == "cpu":
        # cpu_time_seconds 는 누적 counter — vCPU 수로 나눠 0-100% 정규화
        return (
            f"(sum by (instance_id) (rate(libvirt_domain_info_cpu_time_seconds_total[2m]) {join})"
            f" / sum by (instance_id) (libvirt_domain_info_virtual_cpus {join})) * 100"
        )
    if metric == "memory":
        # virtio-balloon 통계가 활성화된 인스턴스에서만 유효
        return f"avg by (instance_id) (libvirt_domain_memory_stats_used_percent {join})"
    if metric == "network_rx":
        return f"sum by (instance_id) (rate(libvirt_domain_interface_stats_receive_bytes_total[2m]) {join})"
    if metric == "network_tx":
        return f"sum by (instance_id) (rate(libvirt_domain_interface_stats_transmit_bytes_total[2m]) {join})"
    if metric == "disk_read":
        return f"sum by (instance_id) (rate(libvirt_domain_block_stats_read_bytes_total[2m]) {join})"
    if metric == "disk_write":
        return f"sum by (instance_id) (rate(libvirt_domain_block_stats_write_bytes_total[2m]) {join})"
    return None  # gpu_util, gpu_mem — DCGM 전용, libvirt 대체 불가


def _resolve_server(conn, instance_id: str):
    try:
        return nova.get_server(conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")


def _authorize(server, token_info: dict) -> None:
    caller_project = token_info.get("project_id", "")
    is_admin = token_info.get("is_system_admin", False)
    if not is_admin and server.project_id != caller_project:
        raise HTTPException(status_code=403, detail="해당 인스턴스에 접근 권한이 없습니다")


def _is_gpu(server) -> bool:
    return (server.flavor_name or "").lower().startswith("gpu.")


# ---------------------------------------------------------------------------
# 단일 메트릭 엔드포인트 (deprecated — batch 엔드포인트 사용 권장)
# ---------------------------------------------------------------------------


@router.get("/{instance_id}/metrics")
async def get_instance_metrics(
    instance_id: str,
    metric: MetricKey = Query(...),
    range: Literal["15m", "1h", "6h", "24h"] = Query("1h"),
    conn=Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """인스턴스의 Prometheus 메트릭 시계열 조회 (단일).

    반환: { instance_id, metric, range, series: [{"ts": int, "value": float}] }
    batch 엔드포인트(/metrics-batch) 사용을 권장합니다.
    """
    server = _resolve_server(conn, instance_id)
    _authorize(server, token_info)

    if metric in _GPU_METRICS and not _is_gpu(server):
        raise HTTPException(status_code=400, detail="GPU 메트릭은 GPU 인스턴스에서만 조회 가능합니다")

    range_s = _RANGE_SECONDS[range]
    end_ts = int(time.time())
    start_ts = end_ts - range_s
    step_s = calc_step(range_s)

    try:
        series = await query_range(_build_expr(metric, server.id), start_ts=start_ts, end_ts=end_ts, step_s=step_s)
        if not series:
            lv_expr = _build_libvirt_expr(metric, server.id)
            if lv_expr:
                series = await query_range(lv_expr, start_ts=start_ts, end_ts=end_ts, step_s=step_s)
    except PromUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Prometheus 연결 불가: {exc}")
    except PromBadQuery as exc:
        raise HTTPException(status_code=500, detail=f"PromQL 오류: {exc}")

    return {"instance_id": instance_id, "metric": metric, "range": range, "series": series}


# ---------------------------------------------------------------------------
# Batch 메트릭 엔드포인트 — Nova/권한 1회, Prometheus N개 병렬
# ---------------------------------------------------------------------------


@router.get("/{instance_id}/metrics-batch")
async def get_instance_metrics_batch(
    instance_id: str,
    metrics: str = Query(..., description="쉼표 구분 메트릭 키: cpu,memory,network_rx,..."),
    range: Literal["15m", "1h", "6h", "24h"] = Query("1h"),
    conn=Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """인스턴스의 Prometheus 메트릭 시계열 일괄 조회.

    Nova 조회 1회, 권한 검증 1회, Prometheus 쿼리 N개 병렬.
    반환: { instance_id, range, metrics: { "<key>": { series, error } } }
    """
    keys = [k.strip() for k in metrics.split(",") if k.strip()]
    if not keys:
        raise HTTPException(status_code=422, detail="metrics 파라미터가 비어있습니다")
    invalid = [k for k in keys if k not in _VALID_METRICS]
    if invalid:
        raise HTTPException(status_code=422, detail=f"알 수 없는 메트릭: {invalid}")

    server = _resolve_server(conn, instance_id)
    _authorize(server, token_info)

    # GPU 메트릭은 GPU 인스턴스만 — batch 에서는 422 대신 silent skip
    if not _is_gpu(server):
        keys = [k for k in keys if k not in _GPU_METRICS]

    range_s = _RANGE_SECONDS[range]
    end_ts = int(time.time())
    start_ts = end_ts - range_s
    step_s = calc_step(range_s)

    async def _one(metric: str) -> tuple[str, dict]:
        try:
            series = await query_range(
                _build_expr(metric, server.id),
                start_ts=start_ts,
                end_ts=end_ts,
                step_s=step_s,
            )
            # node_exporter 미노출 시 libvirt-exporter 폴백 (테넌트망 격리 인스턴스 대응)
            if not series:
                lv_expr = _build_libvirt_expr(metric, server.id)
                if lv_expr:
                    series = await query_range(lv_expr, start_ts=start_ts, end_ts=end_ts, step_s=step_s)
            return metric, {"series": series, "error": None}
        except PromUnavailable as exc:
            return metric, {"series": [], "error": f"prometheus_unavailable: {exc}"}
        except PromBadQuery as exc:
            return metric, {"series": [], "error": f"bad_query: {exc}"}

    results = await asyncio.gather(*(_one(k) for k in keys))
    return {
        "instance_id": instance_id,
        "range": range,
        "metrics": dict(results),
    }
