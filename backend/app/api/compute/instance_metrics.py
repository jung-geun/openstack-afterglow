"""인스턴스별 Prometheus 메트릭 조회."""

from __future__ import annotations

import asyncio
import math
import re
import time
from typing import Literal, get_args

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_os_conn, get_token_info
from app.services import nova
from app.services.prom_query import (
    PromBadQuery,
    PromUnavailable,
    calc_step,
    query_instant_multi,
    query_range,
)

router = APIRouter()

_RANGE_SECONDS: dict[str, int] = {
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
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

# metrics-summary에서 집계할 메트릭 목록 (네트워크 제외)
_SUMMARY_METRICS: tuple[str, ...] = ("cpu", "memory", "disk_read", "disk_write")

# 권장 플레이버 산출 시 최대 사용량 대비 여유율
_RECOMMEND_HEADROOM: float = 1.3


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
    range: Literal["15m", "1h", "6h", "24h", "7d"] = Query("1h"),
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
    range: Literal["15m", "1h", "6h", "24h", "7d"] = Query("1h"),
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


# ---------------------------------------------------------------------------
# 통계 요약 헬퍼
# ---------------------------------------------------------------------------


def _subquery_expr(stat: str, base_expr: str, range_s: int, step_s: int) -> str:
    """avg/min/max_over_time 서브쿼리 instant PromQL 생성."""
    return f"{stat}_over_time(({base_expr})[{range_s}s:{step_s}s])"


async def _fetch_stat(base_expr: str, range_s: int, step_s: int) -> dict[str, float | None]:
    """avg/min/max 3종 병렬 instant 쿼리 → {avg, min, max: float|None}."""

    async def _one(stat: str) -> float | None:
        results = await query_instant_multi(_subquery_expr(stat, base_expr, range_s, step_s))
        return results[0][1] if results else None

    avg_v, min_v, max_v = await asyncio.gather(_one("avg"), _one("min"), _one("max"))
    return {"avg": avg_v, "min": min_v, "max": max_v}


async def _fetch_stat_with_fallback(
    metric: str, instance_id: str, range_s: int, step_s: int
) -> dict[str, float | None]:
    """node_exporter 우선, avg=None이면 libvirt 폴백."""
    result = await _fetch_stat(_build_expr(metric, instance_id), range_s, step_s)
    if result["avg"] is None:
        lv_expr = _build_libvirt_expr(metric, instance_id)
        if lv_expr:
            result = await _fetch_stat(lv_expr, range_s, step_s)
    return result


# ---------------------------------------------------------------------------
# 목록 배지용 일괄 요약 엔드포인트 (literal 경로 — instances_router 보다 먼저 등록됨)
# ---------------------------------------------------------------------------


@router.get("/metrics-summary-batch")
async def get_metrics_summary_batch(
    token_info: dict = Depends(get_token_info),
) -> dict:
    """프로젝트 내 모든 인스턴스의 7일 평균 CPU/메모리 + underutilized 판단.

    반환: { range, prometheus_available, instances: { "<id>": { cpu_avg, mem_avg, underutilized } } }
    """
    project_id = token_info.get("project_id", "")

    # PromQL 라벨 값 주입 방어 — project_id 형식 화이트리스트 검증
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", project_id):
        return {"range": "7d", "prometheus_available": True, "instances": {}}

    range_s = _RANGE_SECONDS["7d"]
    step_s = calc_step(range_s)
    pid = project_id

    cpu_expr_node = (
        f"avg_over_time((100 - avg by (instance_id) "
        f'(rate(node_cpu_seconds_total{{project_id="{pid}",mode="idle"}}[2m])) * 100)'
        f"[{range_s}s:{step_s}s])"
    )
    mem_expr_node = (
        f'avg_over_time(((1 - node_memory_MemAvailable_bytes{{project_id="{pid}"}}'
        f' / node_memory_MemTotal_bytes{{project_id="{pid}"}}) * 100)'
        f"[{range_s}s:{step_s}s])"
    )
    cpu_expr_lv = (
        f"avg_over_time(((sum by (instance_id) (rate(libvirt_domain_info_cpu_time_seconds_total[2m])"
        f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{project_id="{pid}"}}))'
        f" / (sum by (instance_id) (libvirt_domain_info_virtual_cpus"
        f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{project_id="{pid}"}})))'
        f" * 100)[{range_s}s:{step_s}s])"
    )
    mem_expr_lv = (
        f"avg_over_time((avg by (instance_id) (libvirt_domain_memory_stats_used_percent"
        f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{project_id="{pid}"}})'
        f")[{range_s}s:{step_s}s])"
    )

    try:
        node_cpu_res, node_mem_res = await asyncio.gather(
            query_instant_multi(cpu_expr_node),
            query_instant_multi(mem_expr_node),
        )
    except PromUnavailable:
        return {"range": "7d", "prometheus_available": False, "instances": {}}
    except PromBadQuery:
        return {"range": "7d", "prometheus_available": True, "instances": {}}

    cpu_map: dict[str, float] = {labels["instance_id"]: v for labels, v in node_cpu_res if "instance_id" in labels}
    mem_map: dict[str, float] = {labels["instance_id"]: v for labels, v in node_mem_res if "instance_id" in labels}

    # node_exporter 없는 인스턴스는 libvirt 결과로 보충 (node 우선)
    try:
        lv_cpu_res, lv_mem_res = await asyncio.gather(
            query_instant_multi(cpu_expr_lv),
            query_instant_multi(mem_expr_lv),
        )
        for labels, v in lv_cpu_res:
            iid = labels.get("instance_id", "")
            if iid and iid not in cpu_map:
                cpu_map[iid] = v
        for labels, v in lv_mem_res:
            iid = labels.get("instance_id", "")
            if iid and iid not in mem_map:
                mem_map[iid] = v
    except (PromUnavailable, PromBadQuery):
        pass  # libvirt 없으면 node 결과만 사용

    all_ids = set(cpu_map) | set(mem_map)
    instances: dict[str, dict] = {}
    for iid in all_ids:
        cpu_avg = cpu_map.get(iid)
        mem_avg = mem_map.get(iid)
        underutilized = (cpu_avg is not None and cpu_avg < 10) or (mem_avg is not None and mem_avg < 20)
        instances[iid] = {"cpu_avg": cpu_avg, "mem_avg": mem_avg, "underutilized": underutilized}

    return {"range": "7d", "prometheus_available": True, "instances": instances}


# ---------------------------------------------------------------------------
# 인스턴스별 통계 요약 + 리사이즈 권장
# ---------------------------------------------------------------------------


@router.get("/{instance_id}/metrics-summary")
async def get_instance_metrics_summary(
    instance_id: str,
    range: Literal["15m", "1h", "6h", "24h", "7d"] = Query("7d"),
    conn=Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """인스턴스 리소스 사용량 통계(min/avg/max) + 저사용 리사이즈 권장.

    반환: {
      instance_id, range, prometheus_available,
      stats: { cpu/memory/disk_read/disk_write: { min, avg, max } },
      recommendation: { underutilized, reason, current_flavor, suggested_flavor } | null
    }
    """
    server = _resolve_server(conn, instance_id)
    _authorize(server, token_info)

    range_s = _RANGE_SECONDS[range]
    step_s = calc_step(range_s)

    _prom_unavailable = False

    async def _safe_fetch(metric: str) -> dict[str, float | None]:
        nonlocal _prom_unavailable
        try:
            return await _fetch_stat_with_fallback(metric, server.id, range_s, step_s)
        except PromUnavailable:
            _prom_unavailable = True
            return {"avg": None, "min": None, "max": None}
        except PromBadQuery:
            return {"avg": None, "min": None, "max": None}

    stat_results = await asyncio.gather(*(_safe_fetch(m) for m in _SUMMARY_METRICS))

    if _prom_unavailable:
        return {
            "instance_id": instance_id,
            "range": range,
            "prometheus_available": False,
            "stats": {},
            "recommendation": None,
        }

    stats: dict[str, dict[str, float | None]] = {m: r for m, r in zip(_SUMMARY_METRICS, stat_results, strict=True)}

    # 권장 판단 (GPU 인스턴스 제외)
    recommendation = None
    if not _is_gpu(server):
        cpu_avg = stats["cpu"]["avg"]
        mem_avg = stats["memory"]["avg"]

        if cpu_avg is not None or mem_avg is not None:
            underutilized = (cpu_avg is not None and cpu_avg < 10) or (mem_avg is not None and mem_avg < 20)
            if underutilized:
                reason_parts = []
                if cpu_avg is not None and cpu_avg < 10:
                    reason_parts.append("cpu_avg<10")
                if mem_avg is not None and mem_avg < 20:
                    reason_parts.append("mem_avg<20")

                all_flavors = nova.list_flavors(conn)
                cur_flavor = next((f for f in all_flavors if f.id == server.flavor_id), None)

                current_flavor_info = None
                suggested_flavor_info = None

                if cur_flavor:
                    current_flavor_info = {
                        "id": cur_flavor.id,
                        "name": cur_flavor.name,
                        "vcpus": cur_flavor.vcpus,
                        "ram": cur_flavor.ram,
                        "disk": cur_flavor.disk,
                    }

                    cpu_max = stats["cpu"]["max"]
                    mem_max = stats["memory"]["max"]

                    # max 통계 없으면 추천 플레이버를 산출할 수 없음 (권장 문구만)
                    if cpu_max is not None and mem_max is not None:
                        need_vcpus = max(
                            1,
                            math.ceil(cur_flavor.vcpus * cpu_max / 100 * _RECOMMEND_HEADROOM),
                        )
                        need_ram_mb = max(
                            512,
                            math.ceil(cur_flavor.ram * mem_max / 100 * _RECOMMEND_HEADROOM),
                        )
                        candidates = [
                            f
                            for f in all_flavors
                            if not f.is_gpu
                            and f.disk >= cur_flavor.disk  # Nova resize: 디스크 축소 불가
                            and f.vcpus <= cur_flavor.vcpus
                            and f.ram <= cur_flavor.ram
                            and (f.vcpus < cur_flavor.vcpus or f.ram < cur_flavor.ram)
                            and f.vcpus >= need_vcpus
                            and f.ram >= need_ram_mb
                        ]
                        if candidates:
                            best = min(candidates, key=lambda f: (f.vcpus, f.ram, f.disk))
                            suggested_flavor_info = {
                                "id": best.id,
                                "name": best.name,
                                "vcpus": best.vcpus,
                                "ram": best.ram,
                                "disk": best.disk,
                            }

                recommendation = {
                    "underutilized": True,
                    "reason": ",".join(reason_parts),
                    "current_flavor": current_flavor_info,
                    "suggested_flavor": suggested_flavor_info,
                }
            else:
                recommendation = {
                    "underutilized": False,
                    "reason": None,
                    "current_flavor": None,
                    "suggested_flavor": None,
                }

    return {
        "instance_id": instance_id,
        "range": range,
        "prometheus_available": True,
        "stats": stats,
        "recommendation": recommendation,
    }
