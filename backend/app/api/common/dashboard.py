from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio
import logging
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_os_conn
from app.config import get_settings
from app.database import is_db_available
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
):
    """현재 프로젝트의 전체 할당량 (compute/storage/network/file_storage/gpu) 조회."""
    project_id = conn._afterglow_project_id
    settings = get_settings()
    try:
        tasks = [
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
        results = await asyncio.gather(*tasks)
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

            effective, usage = await asyncio.gather(
                get_effective_gpu_quotas(project_id),
                get_project_gpu_usage(conn, project_id),
            )
            for gpu_type, limit in effective.items():
                in_use = usage.get(gpu_type, 0)
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
        from app.api.identity.admin_gpu import _collect_gpu_hosts
        from app.services.keystone import get_admin_connection_for_project

        admin_conn = get_admin_connection_for_project(s.os_project_name)
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
        return await cached_call("afterglow:gpu:availability", ttl_normal(), _collect, refresh=refresh)
    except Exception:
        raise HTTPException(status_code=500, detail="GPU 가용량 조회 실패")


@router.get("/usage")
async def get_project_usage(
    start: str = Query(default=None, description="시작일 YYYY-MM-DD"),
    end: str = Query(default=None, description="종료일 YYYY-MM-DD"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """기간별 프로젝트 리소스 사용량."""
    project_id = conn._afterglow_project_id
    today = date.today()
    end_dt = end or today.isoformat()
    start_dt = start or (today - timedelta(days=30)).isoformat()
    try:
        usage = await asyncio.to_thread(nova.get_project_usage, conn, project_id, start_dt, end_dt)
    except Exception:
        raise HTTPException(status_code=500, detail="작업 실패")
    return {
        "start": start_dt,
        "end": end_dt,
        **usage,
    }
