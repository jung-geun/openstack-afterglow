from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio
import logging
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.exc import OperationalError

from app.api.deps import get_os_conn
from app.config import get_settings
from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.services import cinder, nova
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
        {"id": s.id, "status": s.status, "flavor_id": s.flavor_id, "flavor_name": s.flavor_name}
        for s in nova.list_servers(conn)
    ]


def _list_flavors_as_dicts(conn):
    """플레이버 목록을 dict 리스트로 반환 (캐시 직렬화 호환)."""
    return [{"id": f.id, "name": f.name, "extra_specs": f.extra_specs} for f in nova.list_flavors(conn)]


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
    refresh: bool = Query(False),
):
    project_id = conn._afterglow_project_id

    try:
        servers, compute_limits, volume_limits, all_flavors = await asyncio.gather(
            cached_call(
                f"afterglow:nova:{project_id}:servers",
                ttl_fast(),
                lambda: _list_servers_as_dicts(conn),
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:limits",
                ttl_normal(),
                lambda: nova.get_project_limits(conn),
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:cinder:{project_id}:limits",
                ttl_normal(),
                lambda: cinder.get_volume_limits(conn),
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:flavors",
                ttl_static(),
                lambda: _list_flavors_as_dicts(conn),
                refresh=refresh,
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
        "compute": compute_limits,
        "storage": volume_limits,
        "gpu_used": gpu_used,
    }


@router.get("/config")
async def get_dashboard_config():
    settings = get_settings()
    return {"refresh_interval_ms": settings.refresh_interval_ms}


@router.get("/quotas")
async def get_project_quotas(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
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
            refresh=refresh,
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
    refresh: bool = Query(False),
):
    """GPU 타입별 가용량 조회 (gpu_available_visible=true 시 활성화).

    Placement API를 admin 연결로 조회하여 호스트 상세 없이 타입별 요약만 반환.
    """
    s = get_settings()
    if not s.gpu_available_visible:
        raise HTTPException(status_code=404, detail="GPU 가용량 조회가 비활성화되어 있습니다")

    def _collect():
        import openstack

        from app.api.identity.admin_gpu import _collect_gpu_hosts

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
        data = await cached_call("afterglow:gpu:availability", ttl_normal(), _collect, refresh=refresh)
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
    refresh: bool = Query(False),
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
            refresh=refresh,
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
    refresh: bool = Query(False),
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
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:limits",
                ttl_normal(),
                lambda: nova.get_project_limits(conn),
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:cinder:{project_id}:limits",
                ttl_normal(),
                lambda: cinder.get_volume_limits(conn),
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:neutron:{project_id}:fips",
                ttl_fast(),
                lambda: list(conn.network.ips(project_id=project_id)),
                refresh=refresh,
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
    refresh: bool = Query(False),
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
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:flavors",
                ttl_static(),
                lambda: _list_flavors_as_dicts(conn),
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:cinder:{project_id}:volumes",
                ttl_normal(),
                lambda: [
                    {"id": v.id, "size": v.size or 0, "volume_type": v.volume_type or "standard"}
                    for v in conn.block_storage.volumes()
                ],
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:dashboard:{project_id}:nova_usage:{start_dt}:{end_dt}",
                ttl_fast(),
                lambda: nova.get_project_usage(conn, project_id, start_dt, end_dt),
                refresh=refresh,
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

    # 인스턴스별 vCPU/RAM (active 기준)
    top_instances = []
    for s in servers:
        if s.get("status") != "ACTIVE":
            continue
        fl = flavors_by_id.get(s.get("flavor_id") or "") or flavors_by_name.get(s.get("flavor_name") or "", {})
        top_instances.append({
            "id": s.get("id"),
            "name": s.get("name", ""),
            "flavor": fl.get("name", s.get("flavor_name", "")),
            "vcpus": fl.get("vcpus", 0) if isinstance(fl, dict) else 0,
            "ram_mb": fl.get("ram", 0) if isinstance(fl, dict) else 0,
            "gpu": _gpu_count_from_flavor(fl.get("name", ""), fl.get("extra_specs", {})) if isinstance(fl, dict) else 0,
        })
    top_instances.sort(key=lambda x: x["vcpus"], reverse=True)

    # 볼륨 타입별 집계
    vol_by_type: dict[str, int] = defaultdict(int)
    for v in volumes:
        vol_by_type[v.get("volume_type", "standard")] += v.get("size", 0)

    # Nova usage (instance_hours)
    usage_data = nova_usage if not isinstance(nova_usage, Exception) else {}

    return {
        "range": period,
        "start": start_dt,
        "end": end_dt,
        "top_instances": top_instances[:20],
        "volume_by_type": [{"type": k, "size_gb": v} for k, v in sorted(vol_by_type.items(), key=lambda x: -x[1])],
        "instance_hours": usage_data.get("total_hours", 0) if isinstance(usage_data, dict) else 0,
        "vcpu_hours": usage_data.get("total_vcpu_hours", 0) if isinstance(usage_data, dict) else 0,
    }


@router.get("/usage-report")
async def get_dashboard_usage_report(
    period: str = Query("30d", alias="range", description="7d|14d|30d"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
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
                refresh=refresh,
            ),
            cached_call(
                f"afterglow:nova:{project_id}:quota",
                ttl_normal(),
                lambda: nova.get_project_quota(conn, project_id),
                refresh=refresh,
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

    total_hours = usage.get("total_hours", sum(su.get("hours", 0) for su in server_usages)) if isinstance(usage, dict) else 0.0
    total_vcpu_hours = usage.get("total_vcpu_hours", 0.0) if isinstance(usage, dict) else 0.0

    # 선형 쿼터 예측: 현재 사용률 + 일별 성장률로 30일 후 예측
    vcpus_in_use = quota.get("cores", {}).get("in_use", 0) if isinstance(quota, dict) else 0
    vcpus_limit = quota.get("cores", {}).get("limit", 0) if isinstance(quota, dict) else 0
    forecast_pct = min(100, round((vcpus_in_use / vcpus_limit * 100) if vcpus_limit > 0 else 0, 1))

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
            "forecast_pct": forecast_pct,
        },
    }


@router.get("/activity")
async def get_dashboard_activity(
    period: str = Query("7d", alias="range", description="24h|7d|30d"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
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
                            "created_at": r.created_at.isoformat(),
                        }
                        for r in rows[:50]
                    ]

                    # 고유 사용자 수
                    users_res = await session.execute(
                        select(func.count(func.distinct(AL.user_id)))
                        .where(and_(AL.project_id == project_id, AL.created_at >= since))
                    )
                    kpi["unique_users"] = users_res.scalar() or 0
            except Exception:
                _logger.warning("activity 조회 실패", exc_info=True)

    return {
        "range": period,
        "kpi": kpi,
        "hour_distribution": [{"hour": h, "count": hour_dist[h]} for h in range(24)],
        "recent_actions": recent_actions,
    }
