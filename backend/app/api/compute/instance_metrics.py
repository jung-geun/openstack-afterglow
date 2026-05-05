"""인스턴스별 Prometheus 메트릭 조회 — GET /api/instances/{id}/metrics."""

from __future__ import annotations

import time
from typing import Literal

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

_GPU_METRICS = {"gpu_util", "gpu_mem"}


def _build_expr(metric: str, instance_id: str) -> str:
    # kolla-ansible OpenStack SD 가 부여한 라벨 — instance_id (UUID) 가 unique key.
    # job 필터를 두지 않아 internal/external 두 job 모두 커버한다.
    sel = f'instance_id="{instance_id}"'
    exclude_ifaces = r"lo|veth.*|docker.*|cni.*"
    if metric == "cpu":
        return f'100 - (avg by (instance_id) (rate(node_cpu_seconds_total{{{sel},mode="idle"}}[2m])) * 100)'
    if metric == "memory":
        return (
            f'(1 - node_memory_MemAvailable_bytes{{{sel}}}'
            f' / node_memory_MemTotal_bytes{{{sel}}}) * 100'
        )
    if metric == "network_rx":
        return (
            f"sum by (instance_id) (rate(node_network_receive_bytes_total"
            f'{{{sel},device!~"{exclude_ifaces}"}}[2m]))'
        )
    if metric == "network_tx":
        return (
            f"sum by (instance_id) (rate(node_network_transmit_bytes_total"
            f'{{{sel},device!~"{exclude_ifaces}"}}[2m]))'
        )
    if metric == "disk_read":
        return f'sum by (instance_id) (rate(node_disk_read_bytes_total{{{sel}}}[2m]))'
    if metric == "disk_write":
        return f'sum by (instance_id) (rate(node_disk_written_bytes_total{{{sel}}}[2m]))'
    if metric == "gpu_util":
        return f'avg by (instance_id) (DCGM_FI_DEV_GPU_UTIL{{{sel}}})'
    if metric == "gpu_mem":
        return (
            f'avg by (instance_id) (DCGM_FI_DEV_FB_USED{{{sel}}}'
            f' / DCGM_FI_DEV_FB_TOTAL{{{sel}}}) * 100'
        )
    raise ValueError(f"unknown metric: {metric}")


@router.get("/{instance_id}/metrics")
async def get_instance_metrics(
    instance_id: str,
    metric: MetricKey = Query(...),
    range: Literal["15m", "1h", "6h", "24h"] = Query("1h"),
    conn=Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """인스턴스의 Prometheus 메트릭 시계열 조회.

    반환: { instance_id, metric, range, series: [{"ts": int, "value": float}] }
    """
    # 인스턴스 조회
    try:
        server = nova.get_server(conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")

    # 권한 검증 — 본인 프로젝트 또는 admin
    caller_project = token_info.get("project_id", "")
    is_admin = token_info.get("is_system_admin", False)
    if not is_admin and server.project_id != caller_project:
        raise HTTPException(status_code=403, detail="해당 인스턴스에 접근 권한이 없습니다")

    # GPU 메트릭은 GPU 인스턴스만
    if metric in _GPU_METRICS:
        flavor_name = server.flavor_name or ""
        if not flavor_name.lower().startswith("gpu."):
            raise HTTPException(status_code=400, detail="GPU 메트릭은 GPU 인스턴스에서만 조회 가능합니다")

    # range → timestamps, step
    range_s = _RANGE_SECONDS[range]
    end_ts = int(time.time())
    start_ts = end_ts - range_s
    step_s = calc_step(range_s)

    # PromQL 실행 — kolla-ansible OpenStack SD 가 부여한 instance_id (UUID) 라벨로 필터.
    # IP 기반 셀렉터(instance="IP:9100") 는 kolla 가 instance 라벨을 인스턴스 이름으로 재라벨링하므로 매칭되지 않는다.
    expr = _build_expr(metric, server.id)
    try:
        series = await query_range(expr, start_ts=start_ts, end_ts=end_ts, step_s=step_s)
    except PromUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Prometheus 연결 불가: {exc}")
    except PromBadQuery as exc:
        raise HTTPException(status_code=500, detail=f"PromQL 오류: {exc}")

    return {"instance_id": instance_id, "metric": metric, "range": range, "series": series}
