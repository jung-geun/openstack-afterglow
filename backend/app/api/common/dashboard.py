from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio
import logging
import math
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.exc import OperationalError

from app.api.deps import CacheMode, cache_mode, get_os_conn
from app.config import get_settings
from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.services import cinder, nova, prom_query
from app.services import manila as manila_svc
from app.services import neutron as neutron_svc
from app.services import swift as swift_svc
from app.services import trove as trove_svc
from app.services.cache import cached_call, ttl_fast, ttl_normal, ttl_static

router = APIRouter()
_logger = logging.getLogger(__name__)


def _list_servers_as_dicts(conn):
    """서버 목록을 dict 리스트로 반환 (캐시 직렬화 호환)."""
    return [
        {
            "id": s.id,
            "name": getattr(s, "name", "") or "",
            "status": s.status,
            "flavor_id": s.flavor_id,
            "flavor_name": s.flavor_name,
            "created_at": getattr(s, "created_at", None),
        }
        for s in nova.list_servers(conn)
    ]


def _list_flavors_as_dicts(conn):
    """플레이버 목록을 dict 리스트로 반환 (캐시 직렬화 호환)."""
    return [
        {
            "id": f.id,
            "name": f.name,
            "vcpus": f.vcpus,
            "ram": f.ram,
            "disk": f.disk,
            "extra_specs": f.extra_specs,
        }
        for f in nova.list_flavors(conn)
    ]


def _usage_hours(created_at: str | None) -> float:
    """created_at ISO 문자열 → 현재까지 경과 시간(hours), 파싱 실패 시 0.0."""
    if not created_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return max(0.0, round((datetime.now(UTC) - dt).total_seconds() / 3600, 1))
    except Exception:
        return 0.0


def _gpu_count_from_flavor(name: str, extra_specs: dict) -> int:
    # 1차: pci_passthrough:alias 에서 GPU 디바이스 카운트 (audio 제외)
    alias = extra_specs.get("pci_passthrough:alias", "")
    if alias:
        count = 0
        for entry in alias.split(","):
            entry = entry.strip()
            if ":" not in entry:
                continue
            dev, num = entry.rsplit(":", 1)
            if "audio" in dev.lower():
                continue
            try:
                count += int(num)
            except ValueError:
                count += 1
        if count > 0:
            return count
    # 2차: :category 키에 gpu 포함 여부
    cat = extra_specs.get(":category", "")
    if "gpu" in cat.lower():
        return 1
    # 3차: 이름 기반 fallback
    m = re.match(r"^gpu[._]\w+?(?:x(\d+))?[._]", name)
    if m:
        return int(m.group(1)) if m.group(1) else 1
    return 0


@router.get("/summary")
async def get_dashboard_summary(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    project_id = conn._afterglow_project_id

    try:
        servers, all_flavors = await asyncio.gather(
            cached_call(
                f"afterglow:nova:{project_id}:servers",
                ttl_fast(),
                lambda: _list_servers_as_dicts(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:flavors",
                ttl_static(),
                lambda: _list_flavors_as_dicts(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
        )
    except Exception:
        raise HTTPException(status_code=500, detail="작업 실패")

    flavors_by_id: dict = {f["id"]: f for f in all_flavors}
    flavors_by_name: dict = {f["name"]: f for f in all_flavors}

    gpu_used = 0
    for s in servers:
        if s["status"] != "ACTIVE":
            continue
        fl = flavors_by_id.get(s.get("flavor_id") or "", {})
        if not fl and s.get("flavor_name"):
            fl = flavors_by_name.get(s["flavor_name"], {})
        gpu_used += _gpu_count_from_flavor(fl.get("name", ""), fl.get("extra_specs", {}))

    return {
        "instances": {
            "total": len(servers),
            "active": sum(1 for s in servers if s["status"] == "ACTIVE"),
            "shutoff": sum(1 for s in servers if s["status"] == "SHUTOFF"),
            "error": sum(1 for s in servers if s["status"] == "ERROR"),
        },
        "gpu_used": gpu_used,
    }


@router.get("/config")
async def get_dashboard_config():
    settings = get_settings()
    return {"refresh_interval_ms": settings.refresh_interval_ms}


@router.get("/quotas")
async def get_project_quotas(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """현재 프로젝트의 전체 할당량 (compute/storage/network/file_storage/gpu) 조회."""
    project_id = conn._afterglow_project_id
    settings = get_settings()

    async def _fetch_quotas():
        tasks: list = [
            asyncio.to_thread(nova.get_project_quota, conn, project_id),
            asyncio.to_thread(cinder.get_volume_quota, conn, project_id),
            asyncio.to_thread(neutron_svc.get_network_quota, conn, project_id),
        ]
        if settings.service_manila_enabled:
            tasks.append(asyncio.to_thread(manila_svc.get_file_storage_quota, conn))
        if settings.service_trove_enabled:
            tasks.append(asyncio.to_thread(trove_svc.count_instances, conn))
        if settings.service_swift_enabled:
            tasks.append(asyncio.to_thread(swift_svc.get_account_metadata, conn))
        return list(await asyncio.gather(*tasks))

    try:
        results = await cached_call(
            f"afterglow:dashboard:{project_id}:quotas",
            ttl_normal(),
            _fetch_quotas,
            enabled=cm.enabled,
            refresh=cm.refresh,
        )
        compute_q, volume_q, network_q = results[0], results[1], results[2]
        idx = 3
        file_storage_q = results[idx] if settings.service_manila_enabled else {"limit": 0, "in_use": 0, "reserved": 0}
        if settings.service_manila_enabled:
            idx += 1
        trove_count: int = results[idx] if settings.service_trove_enabled else 0
        if settings.service_trove_enabled:
            idx += 1
        swift_meta: dict = (
            results[idx]
            if settings.service_swift_enabled
            else {"container_count": 0, "object_count": 0, "bytes_used": 0}
        )
    except Exception:
        raise HTTPException(status_code=500, detail="작업 실패")

    # GPU quota (DB 있는 경우)
    gpu_quota: list[dict] = []
    if is_db_available():
        try:
            from app.services.gpu_quota import get_effective_gpu_quotas, get_project_gpu_usage

            effective_result, usage_result = await asyncio.gather(
                get_effective_gpu_quotas(project_id),
                get_project_gpu_usage(conn, project_id),
                return_exceptions=True,
            )
            if isinstance(effective_result, Exception) or isinstance(usage_result, Exception):
                _logger.warning("GPU quota 조회 부분 실패: effective=%r usage=%r", effective_result, usage_result)
                if isinstance(effective_result, OperationalError) or isinstance(usage_result, OperationalError):
                    mark_db_unhealthy()
            else:
                for gpu_type, limit in effective_result.items():
                    in_use = usage_result.get(gpu_type, 0)
                    gpu_quota.append(
                        {
                            "gpu_type": gpu_type,
                            "limit": limit,
                            "in_use": in_use,
                            "available": (limit - in_use) if limit >= 0 else -1,
                        }
                    )
        except Exception:
            _logger.warning("GPU quota 조회 실패", exc_info=True)

    return {
        "compute": compute_q,
        "storage": volume_q,
        "network": network_q,
        "file_storage": file_storage_q,
        "gpu": gpu_quota,
        "database": {"instances_count": trove_count},
        "object_storage": swift_meta,
    }


@router.get("/gpu-available")
async def get_gpu_available(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """GPU 타입별 가용량 조회 (gpu_available_visible=true 시 활성화).

    Placement API를 admin 연결로 조회하여 호스트 상세 없이 타입별 요약만 반환.
    """
    s = get_settings()
    if not s.gpu_available_visible:
        raise HTTPException(status_code=404, detail="GPU 가용량 조회가 비활성화되어 있습니다")

    def _collect():
        import openstack

        from app.services.gpu_inventory import _collect_gpu_hosts

        # get_admin_connection_for_project()는 project_id(UUID)를 기대하므로
        # admin project는 project_name으로 직접 연결 생성 (gpu_quota.py와 동일 패턴)
        admin_conn = openstack.connect(
            load_envvars=False,
            load_yaml_config=False,
            auth_url=s.os_auth_url,
            auth_type="password",
            username=s.os_username,
            password=s.os_password,
            project_name=s.os_project_name,
            user_domain_name=s.os_user_domain_name,
            project_domain_name=s.os_project_domain_name,
            region_name=s.os_region_name,
            interface=s.os_interface,
            api_timeout=30,
            verify=s.ssl_verify,
        )
        data = _collect_gpu_hosts(admin_conn)
        return {
            "gpu_types": [
                {
                    "device_name": t["device_name"],
                    "vendor": t["vendor"],
                    "total": t["total"],
                    "used": t["used"],
                    "available": t["total"] - t["used"],
                }
                for t in data["gpu_types"]
            ],
            "summary": data["summary"],
        }

    try:
        data = await cached_call(
            "afterglow:gpu:availability", ttl_normal(), _collect, enabled=cm.enabled, refresh=cm.refresh
        )
    except Exception:
        _logger.warning("GPU 가용량 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="GPU 가용량 조회 실패")

    # 프로젝트 GPU 쿼터 기반 필터링 + 가용량을 쿼터 상한 기준으로 표시
    if is_db_available():
        try:
            from app.api.identity.admin_gpu import build_device_name_to_alias_map
            from app.services.gpu_quota import get_effective_gpu_quotas, get_project_gpu_usage

            project_id = conn._afterglow_project_id
            quotas = await get_effective_gpu_quotas(project_id)
            usage = await get_project_gpu_usage(conn, project_id)
            name_to_alias = build_device_name_to_alias_map()

            filtered = []
            for t in data["gpu_types"]:
                alias = name_to_alias.get(t["device_name"], "")
                limit = quotas.get(alias, 0)
                if limit == 0:
                    continue
                in_use = usage.get(alias, 0)
                if limit == -1:
                    # 무제한: 클러스터 전체 수치 그대로 사용
                    filtered.append(t)
                else:
                    # 상한 있음: total=쿼터 상한, available=min(쿼터 잔여, 클러스터 잔여)
                    quota_remaining = max(limit - in_use, 0)
                    filtered.append(
                        {
                            **t,
                            "total": limit,
                            "used": in_use,
                            "available": min(quota_remaining, t["available"]),
                        }
                    )
            data = {**data, "gpu_types": filtered}
        except Exception:
            _logger.warning("GPU 쿼터 필터링 실패 — 전체 목록 반환", exc_info=True)

    return data


@router.get("/usage")
async def get_project_usage(
    start: str = Query(default=None, description="시작일 YYYY-MM-DD"),
    end: str = Query(default=None, description="종료일 YYYY-MM-DD"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """기간별 프로젝트 리소스 사용량."""
    project_id = conn._afterglow_project_id
    today = date.today()
    end_dt = end or today.isoformat()
    start_dt = start or (today - timedelta(days=30)).isoformat()
    try:
        usage = await cached_call(
            f"afterglow:dashboard:{project_id}:usage:{start_dt}:{end_dt}",
            ttl_fast(),
            lambda: nova.get_project_usage(conn, project_id, start_dt, end_dt),
            enabled=cm.enabled,
            refresh=cm.refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="작업 실패")
    return {
        "start": start_dt,
        "end": end_dt,
        **usage,
    }


# ---------------------------------------------------------------------------
# Phase 50 신규 엔드포인트 (4-A ~ 4-D)
# ---------------------------------------------------------------------------


def _range_to_dates(range_str: str) -> tuple[str, str]:
    """range=24h|7d|14d|30d → (start_iso, end_iso)."""
    today = date.today()
    days = {"24h": 1, "7d": 7, "14d": 14, "30d": 30}.get(range_str, 30)
    return (today - timedelta(days=days)).isoformat(), today.isoformat()


@router.get("/overview")
async def get_dashboard_overview(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """대시보드 개요: StatTile 6종 + 최근 인스턴스 8 + 실행 중 태스크."""
    project_id = conn._afterglow_project_id
    settings = get_settings()

    try:
        servers, compute_lim, volume_lim, fips = await asyncio.gather(
            cached_call(
                f"afterglow:nova:{project_id}:servers",
                ttl_fast(),
                lambda: _list_servers_as_dicts(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:limits",
                ttl_normal(),
                lambda: nova.get_project_limits(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:cinder:{project_id}:limits",
                ttl_normal(),
                lambda: cinder.get_volume_limits(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:neutron:{project_id}:fips",
                ttl_fast(),
                lambda: list(conn.network.ips(project_id=project_id)),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            return_exceptions=True,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="개요 조회 실패")

    if isinstance(servers, Exception):
        servers = []
    if isinstance(fips, Exception):
        fips = []

    c_limits = compute_lim if not isinstance(compute_lim, Exception) else {}
    v_limits = volume_lim if not isinstance(volume_lim, Exception) else {}

    error_instances = [s for s in servers if s.get("status") == "ERROR"]
    recent = sorted(servers, key=lambda s: s.get("status", ""), reverse=False)[-8:]

    # k3s 클러스터 수 (선택적)
    k3s_count = 0
    k3s_active = 0
    if settings.service_k3s_enabled:
        try:
            from app.services import k3s_cluster

            clusters = await asyncio.to_thread(k3s_cluster.list_clusters_for_project, conn, project_id)
            k3s_count = len(clusters)
            k3s_active = sum(1 for c in clusters if c.get("status") == "CREATE_COMPLETE")
        except Exception:
            pass

    alerts = []
    if error_instances:
        alerts.append({"type": "error", "message": f"오류 상태 인스턴스 {len(error_instances)}개"})

    vcpus_used = c_limits.get("cores", {}).get("in_use", 0) if isinstance(c_limits, dict) else 0
    vcpus_total = c_limits.get("cores", {}).get("limit", 0) if isinstance(c_limits, dict) else 0
    ram_used = c_limits.get("ram", {}).get("in_use", 0) if isinstance(c_limits, dict) else 0
    ram_total = c_limits.get("ram", {}).get("limit", 0) if isinstance(c_limits, dict) else 0
    storage_used = v_limits.get("gigabytes", {}).get("in_use", 0) if isinstance(v_limits, dict) else 0
    storage_total = v_limits.get("gigabytes", {}).get("limit", 0) if isinstance(v_limits, dict) else 0

    return {
        "stats": {
            "instances_total": len(servers),
            "instances_active": sum(1 for s in servers if s.get("status") == "ACTIVE"),
            "k3s_clusters": k3s_count,
            "k3s_active": k3s_active,
            "vcpus_used": vcpus_used,
            "vcpus_total": vcpus_total,
            "ram_used_mb": ram_used,
            "ram_total_mb": ram_total,
            "storage_used_gb": storage_used,
            "storage_total_gb": storage_total,
            "floating_ips": len(fips) if isinstance(fips, list) else 0,
        },
        "recent_instances": recent,
        "alerts": alerts,
    }


@router.get("/usage-stats")
async def get_dashboard_usage_stats(
    period: str = Query("30d", alias="range", description="24h|7d|14d|30d"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """사용량 분석: 인스턴스별 사용량 + OS 분포 + 볼륨 타입별 용량."""
    project_id = conn._afterglow_project_id
    start_dt, end_dt = _range_to_dates(period)

    try:
        servers, flavors, volumes, nova_usage = await asyncio.gather(
            cached_call(
                f"afterglow:nova:{project_id}:servers",
                ttl_fast(),
                lambda: _list_servers_as_dicts(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:flavors",
                ttl_static(),
                lambda: _list_flavors_as_dicts(conn),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:cinder:{project_id}:volumes",
                ttl_normal(),
                lambda: [
                    {"id": v.id, "size": v.size or 0, "volume_type": v.volume_type or "standard"}
                    for v in conn.block_storage.volumes()
                ],
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:dashboard:{project_id}:nova_usage:{start_dt}:{end_dt}",
                ttl_fast(),
                lambda: nova.get_project_usage(conn, project_id, start_dt, end_dt),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            return_exceptions=True,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="사용량 조회 실패")

    if isinstance(servers, Exception):
        servers = []
    if isinstance(flavors, Exception):
        flavors = []
    if isinstance(volumes, Exception):
        volumes = []

    flavors_by_id = {f["id"]: f for f in flavors}
    flavors_by_name = {f["name"]: f for f in flavors}

    # 인스턴스별 vCPU/RAM (모든 상태 포함, vCPU 내림차순)
    top_instances = []
    for s in servers:
        fl = flavors_by_id.get(s.get("flavor_id") or "") or flavors_by_name.get(s.get("flavor_name") or "", {})
        fl_vcpus = fl.get("vcpus", 0) if isinstance(fl, dict) else 0
        fl_ram = fl.get("ram", 0) if isinstance(fl, dict) else 0
        fl_disk = fl.get("disk", 0) if isinstance(fl, dict) else 0
        fl_name = fl.get("name", s.get("flavor_name", "")) if isinstance(fl, dict) else s.get("flavor_name", "")
        fl_extra = fl.get("extra_specs", {}) if isinstance(fl, dict) else {}
        top_instances.append(
            {
                "id": s.get("id"),
                "name": s.get("name", ""),
                "flavor_name": fl_name,
                "vcpus": fl_vcpus,
                "ram_mb": fl_ram,
                "disk_gb": fl_disk,
                "status": s.get("status", "ACTIVE"),
                "usage_hours": _usage_hours(s.get("created_at")),
                "gpu": _gpu_count_from_flavor(fl_name, fl_extra),
            }
        )
    top_instances.sort(key=lambda x: x["vcpus"], reverse=True)
    top20 = top_instances[:20]

    # 인스턴스별 실 사용률 — libvirt instant query (Prometheus 미가용 시 silent fallback)
    uuids = [inst["id"] for inst in top20 if inst.get("id")]
    cpu_by_id: dict[str, float] = {}
    ram_by_id: dict[str, float] = {}
    if uuids:
        uuid_re = "|".join(uuids)
        cpu_expr = (
            f"sum by (instance_id) (rate(libvirt_domain_info_cpu_time_seconds_total[2m])"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
            f" / sum by (instance_id) (libvirt_domain_info_virtual_cpus"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
            f" * 100"
        )
        ram_expr = (
            f"avg by (instance_id) (libvirt_domain_memory_stats_used_percent"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
        )
        try:
            cpu_results, ram_results = await asyncio.gather(
                prom_query.query_instant_multi(cpu_expr),
                prom_query.query_instant_multi(ram_expr),
            )
            cpu_by_id = {
                lbl["instance_id"]: round(v, 1) for lbl, v in cpu_results if "instance_id" in lbl and not math.isnan(v)
            }
            ram_by_id = {
                lbl["instance_id"]: round(v, 1) for lbl, v in ram_results if "instance_id" in lbl and not math.isnan(v)
            }
        except Exception:
            pass
    for inst in top20:
        inst["cpu_pct"] = cpu_by_id.get(inst["id"])
        inst["ram_pct"] = ram_by_id.get(inst["id"])

    # 볼륨 타입별 집계
    vol_by_type: dict[str, int] = defaultdict(int)
    vol_count_by_type: dict[str, int] = defaultdict(int)
    for v in volumes:
        vtype = v.get("volume_type", "standard")
        vol_by_type[vtype] += v.get("size", 0)
        vol_count_by_type[vtype] += 1

    # Nova usage (instance_hours)
    usage_data = nova_usage if not isinstance(nova_usage, Exception) else {}

    return {
        "range": period,
        "start": start_dt,
        "end": end_dt,
        "top_instances": top20,
        "volumes_by_type": [
            {"type": k, "total_gb": v, "count": vol_count_by_type[k]}
            for k, v in sorted(vol_by_type.items(), key=lambda x: -x[1])
        ],
        "instance_hours": usage_data.get("total_hours", 0) if isinstance(usage_data, dict) else 0,
        "vcpu_hours": usage_data.get("total_vcpu_hours", 0) if isinstance(usage_data, dict) else 0,
    }


@router.get("/usage-report")
async def get_dashboard_usage_report(
    response: Response,
    period: str = Query("30d", alias="range", description="7d|14d|30d"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """사용량 리포트: 기간별 일별 사용량 + flavor 시간 + 쿼터 예측."""
    project_id = conn._afterglow_project_id
    today = date.today()
    days = {"7d": 7, "14d": 14, "30d": 30}.get(period, 30)
    start_dt = (today - timedelta(days=days)).isoformat()
    end_dt = today.isoformat()

    try:
        nova_usage, compute_q = await asyncio.gather(
            cached_call(
                f"afterglow:dashboard:{project_id}:nova_usage:{start_dt}:{end_dt}",
                ttl_fast(),
                lambda: nova.get_project_usage(conn, project_id, start_dt, end_dt),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:quota",
                ttl_normal(),
                lambda: nova.get_project_quota(conn, project_id),
                enabled=cm.enabled,
                refresh=cm.refresh,
            ),
            return_exceptions=True,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="사용량 리포트 조회 실패")

    usage = nova_usage if not isinstance(nova_usage, Exception) else {}
    quota = compute_q if not isinstance(compute_q, Exception) else {}

    # 서버별 사용 시간 → flavor 집계
    server_usages = usage.get("server_usages", []) if isinstance(usage, dict) else []
    flavor_map: dict[str, dict] = {}
    for su in server_usages:
        fname = su.get("flavor", "unknown")
        if fname not in flavor_map:
            flavor_map[fname] = {"flavor": fname, "instance_count": 0, "usage_hours": 0.0}
        flavor_map[fname]["instance_count"] += 1
        flavor_map[fname]["usage_hours"] += su.get("hours", 0.0)

    total_hours = (
        usage.get("total_hours", sum(su.get("hours", 0) for su in server_usages)) if isinstance(usage, dict) else 0.0
    )
    total_vcpu_hours = usage.get("total_vcpu_hours", 0.0) if isinstance(usage, dict) else 0.0

    # 쿼터 조회
    cores_q = quota.get("cores", {}) if isinstance(quota, dict) else {}
    ram_q = quota.get("ram", {}) if isinstance(quota, dict) else {}
    storage_q = quota.get("gigabytes", {}) if isinstance(quota, dict) else {}

    vcpus_in_use = cores_q.get("in_use", 0)
    vcpus_limit = cores_q.get("limit", 0)
    ram_in_use = ram_q.get("in_use", 0)
    ram_limit = ram_q.get("limit", 0)
    storage_in_use = storage_q.get("in_use", 0)
    storage_limit = storage_q.get("limit", 0)

    def _pct(used: float, limit: float) -> float:
        return min(100.0, round((used / limit * 100) if limit > 0 else 0.0, 1))

    response.headers["Cache-Control"] = "private, max-age=60"
    return {
        "range": period,
        "start": start_dt,
        "end": end_dt,
        "stats": {
            "instance_hours": round(float(total_hours), 2),
            "vcpu_hours": round(float(total_vcpu_hours), 2),
            "active_instances": len([s for s in server_usages if s.get("state") == "active"]),
            "total_instances": len(server_usages),
        },
        "flavor_hours": sorted(flavor_map.values(), key=lambda x: -x["usage_hours"])[:15],
        "quota": {
            "vcpus_in_use": vcpus_in_use,
            "vcpus_limit": vcpus_limit,
        },
        "forecast": {
            "vcpu_pct": _pct(vcpus_in_use, vcpus_limit),
            "memory_pct": _pct(ram_in_use, ram_limit),
            "storage_pct": _pct(storage_in_use, storage_limit),
        },
    }


@router.get("/metrics/trend")
async def get_dashboard_metrics_trend(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    range_: str = Query("14d", alias="range", description="24h|7d|14d"),
    cm: CacheMode = Depends(cache_mode),
):
    """vCPU/메모리/스토리지/네트워크 추세 (PromQL).

    range 별 step: 24h=5분(288pt), 7d=1시간(168pt), 14d=6시간(56pt).
    스토리지는 인스턴스 root fs 사용률 %(node_exporter) — Cinder 볼륨 아님.
    Prometheus 미설치 시 prometheus_available=false.
    """
    if range_ not in ("24h", "7d", "14d"):
        raise HTTPException(status_code=400, detail=f"유효하지 않은 range: {range_}. 허용값: 24h, 7d, 14d")

    project_id = conn._afterglow_project_id

    _RANGE_CFG = {
        "24h": {"seconds": 86400, "step": 300, "ttl": 15},
        "7d": {"seconds": 7 * 86400, "step": 3600, "ttl": 120},
        "14d": {"seconds": 14 * 86400, "step": 6 * 3600, "ttl": 300},
    }
    cfg = _RANGE_CFG[range_]
    cache_key = f"afterglow:dashboard:trend:{project_id}:{range_}"

    async def _query_all() -> dict:
        now = int(datetime.now(UTC).timestamp())
        start = now - cfg["seconds"]
        step = cfg["step"]

        def _vals(series: list[dict]) -> list[float]:
            return [round(p["value"], 2) for p in series if not math.isnan(p["value"])]

        async def _safe_query(expr: str) -> list[float]:
            try:
                series = await prom_query.query_range(expr, start_ts=start, end_ts=now, step_s=step)
                return _vals(series)
            except Exception:
                return []

        # 프로젝트 인스턴스 UUID 리스트 수집 — libvirt 조인에 사용 (networks.py:488 패턴)
        uuids = [s.id for s in conn.compute.servers() if s.id]
        empty: list[float] = []
        if not uuids:
            return {
                "vcpu": {"data": empty, "points": 0, "available": False},
                "memory": {"data": empty, "points": 0, "available": False},
                "storage": {"data": empty, "points": 0, "available": False},
                "network": {"data": empty, "points": 0, "available": False, "unit": "KiB/s"},
                "prometheus_available": False,
                "range": range_,
            }
        uuid_re = "|".join(uuids)  # UUID는 [0-9a-f-]만 — re.escape 불필요

        # vCPU: libvirt cpu_time / virtual_cpus, instance_id 조인 (모든 인스턴스 커버)
        vcpu_expr = (
            f"sum(rate(libvirt_domain_info_cpu_time_seconds_total[5m])"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
            f" / sum(libvirt_domain_info_virtual_cpus"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
            f" * 100"
        )
        # RAM: virtio-balloon stats_used_percent 평균 (미활성 인스턴스는 자연 제외)
        mem_expr = (
            f"avg(libvirt_domain_memory_stats_used_percent"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
        )
        # Storage: node_exporter root fs 사용률 % (libvirt에 디스크 사용률 메트릭 없음)
        storage_expr = (
            f'(1 - sum(node_filesystem_avail_bytes{{project_id="{project_id}",mountpoint="/",'
            f'fstype!~"tmpfs|overlay|squashfs|devtmpfs"}})'
            f' / sum(node_filesystem_size_bytes{{project_id="{project_id}",mountpoint="/",'
            f'fstype!~"tmpfs|overlay|squashfs|devtmpfs"}})) * 100'
        )
        # Network: libvirt interface_stats + instance_id 조인 KiB/s (prometheus_available 판정 제외)
        net_expr = (
            f"(sum(rate(libvirt_domain_interface_stats_receive_bytes_total[5m])"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}})'
            f" + sum(rate(libvirt_domain_interface_stats_transmit_bytes_total[5m])"
            f' * on (domain) group_left(instance_id) libvirt_domain_openstack_info{{instance_id=~"{uuid_re}"}}))'
            f" / 1024"
        )

        vcpu_data, mem_data, storage_data, net_data = await asyncio.gather(
            _safe_query(vcpu_expr),
            _safe_query(mem_expr),
            _safe_query(storage_expr),
            _safe_query(net_expr),
        )

        prometheus_available = any([vcpu_data, mem_data, storage_data])
        return {
            "vcpu": {"data": vcpu_data, "points": len(vcpu_data), "available": bool(vcpu_data)},
            "memory": {"data": mem_data, "points": len(mem_data), "available": bool(mem_data)},
            "storage": {"data": storage_data, "points": len(storage_data), "available": bool(storage_data)},
            "network": {"data": net_data, "points": len(net_data), "available": bool(net_data), "unit": "KiB/s"},
            "prometheus_available": prometheus_available,
            "range": range_,
        }

    return await cached_call(cache_key, cfg["ttl"], _query_all, enabled=cm.enabled, refresh=cm.refresh)


@router.get("/activity")
async def get_dashboard_activity(
    period: str = Query("7d", alias="range", description="24h|7d|30d"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    """활동 현황: KPI + 시간대 분포 + 최근 감사 로그."""
    project_id = conn._afterglow_project_id
    start_dt, end_dt = _range_to_dates(period)
    start_dt_obj = date.fromisoformat(start_dt)

    hour_dist = [0] * 24
    recent_actions: list[dict] = []
    kpi = {"total": 0, "success": 0, "failed": 0, "last_24h": 0, "unique_users": 0}

    if is_db_available():
        factory = get_session_factory()
        if factory:
            try:
                from app.models.activity import ActivityLog as AL

                since = datetime(start_dt_obj.year, start_dt_obj.month, start_dt_obj.day, tzinfo=UTC)
                since_24h = datetime.now(UTC) - timedelta(hours=24)
                async with factory() as session:
                    # 기간 내 전체 로그
                    rows_res = await session.execute(
                        select(AL)
                        .where(and_(AL.project_id == project_id, AL.created_at >= since))
                        .order_by(AL.id.desc())
                        .limit(200)
                    )
                    rows = rows_res.scalars().all()

                    for r in rows:
                        hour_dist[r.created_at.hour] += 1
                        kpi["total"] += 1
                        if r.status == "success":
                            kpi["success"] += 1
                        elif r.status == "failed":
                            kpi["failed"] += 1
                        if r.created_at >= since_24h:
                            kpi["last_24h"] += 1

                    recent_actions = [
                        {
                            "id": r.id,
                            "action": r.action,
                            "resource_type": r.resource_type,
                            "resource_name": r.resource_name,
                            "status": r.status,
                            "username": r.username,
                            "created_at": r.created_at.isoformat() + "Z",
                        }
                        for r in rows[:50]
                    ]

                    # 고유 사용자 수
                    users_res = await session.execute(
                        select(func.count(func.distinct(AL.user_id))).where(
                            and_(AL.project_id == project_id, AL.created_at >= since)
                        )
                    )
                    kpi["unique_users"] = users_res.scalar() or 0
            except Exception:
                _logger.warning("activity 조회 실패", exc_info=True)

    return {
        "range": period,
        "kpi": kpi,
        "hour_distribution": hour_dist,
        "recent_actions": recent_actions,
        "db_status": "ok" if is_db_available() else "unavailable",
    }


@router.get("/notifications")
async def get_dashboard_notifications(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 프로젝트의 사용자 알림 — ERROR 인스턴스 + 쿼터 임박/초과."""
    project_id = conn._afterglow_project_id
    notifications: list[dict] = []

    servers, compute_limits, volume_limits = await asyncio.gather(
        cached_call(f"afterglow:nova:{project_id}:servers", ttl_fast(), lambda: _list_servers_as_dicts(conn)),
        cached_call(f"afterglow:nova:{project_id}:limits", ttl_normal(), lambda: nova.get_project_limits(conn)),
        cached_call(f"afterglow:cinder:{project_id}:limits", ttl_normal(), lambda: cinder.get_volume_limits(conn)),
        return_exceptions=True,
    )

    # ERROR 인스턴스
    if not isinstance(servers, Exception):
        error_count = sum(1 for s in servers if s.get("status") == "ERROR")
        if error_count > 0:
            notifications.append(
                {
                    "type": "instance_error",
                    "severity": "danger",
                    "message": f"오류 상태 인스턴스 {error_count}개",
                    "count": error_count,
                }
            )

    # 컴퓨트 쿼터 경고
    def _quota_notif(resource: str, used: int, limit: int) -> dict | None:
        if limit <= 0:
            return None
        pct = used / limit
        if pct >= 1.0:
            return {
                "type": f"quota_full_{resource}",
                "severity": "danger",
                "message": f"{resource} 쿼터 가득 참 ({used}/{limit})",
                "count": 1,
            }
        if pct >= 0.9:
            return {
                "type": f"quota_warn_{resource}",
                "severity": "warning",
                "message": f"{resource} 쿼터 {int(pct * 100)}% 사용 ({used}/{limit})",
                "count": 1,
            }
        return None

    if isinstance(compute_limits, dict):
        for key, label in (("instances", "인스턴스"), ("cores", "vCPU"), ("ram", "RAM")):
            q = compute_limits.get(key, {})
            if isinstance(q, dict):
                n = _quota_notif(label, q.get("in_use", 0), q.get("limit", 0))
                if n:
                    notifications.append(n)

    if isinstance(volume_limits, dict):
        q = volume_limits.get("gigabytes", {})
        if isinstance(q, dict):
            n = _quota_notif("스토리지(GB)", q.get("in_use", 0), q.get("limit", 0))
            if n:
                notifications.append(n)

    return {"notifications": notifications}
