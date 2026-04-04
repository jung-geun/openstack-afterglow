import asyncio
import re
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.config import get_settings
from app.services import nova, cinder
from app.services.cache import cached_call

router = APIRouter()


def _list_servers_as_dicts(conn):
    """서버 목록을 dict 리스트로 반환 (캐시 직렬화 호환)."""
    return [
        {"id": s.id, "status": s.status, "flavor_id": s.flavor_id}
        for s in nova.list_servers(conn)
    ]


def _list_flavors_as_dicts(conn):
    """플레이버 목록을 dict 리스트로 반환 (캐시 직렬화 호환)."""
    return [
        {"id": f.id, "name": f.name, "extra_specs": f.extra_specs}
        for f in nova.list_flavors(conn)
    ]


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
    m = re.match(r'^gpu[._]\w+?(?:x(\d+))?[._]', name)
    if m:
        return int(m.group(1)) if m.group(1) else 1
    return 0


@router.get("/summary")
async def get_dashboard_summary(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    project_id = conn._union_project_id

    try:
        servers, compute_limits, volume_limits, all_flavors = await asyncio.gather(
            cached_call(
                f"union:nova:{project_id}:servers", 15,
                lambda: _list_servers_as_dicts(conn),
            ),
            cached_call(
                f"union:nova:{project_id}:limits", 30,
                lambda: nova.get_project_limits(conn),
            ),
            cached_call(
                f"union:cinder:{project_id}:limits", 30,
                lambda: cinder.get_volume_limits(conn),
            ),
            cached_call(
                f"union:nova:{project_id}:flavors", 300,
                lambda: _list_flavors_as_dicts(conn),
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    flavors_by_id: dict = {f["id"]: f for f in all_flavors}

    gpu_used = 0
    for s in servers:
        if s["status"] != "ACTIVE":
            continue
        fl = flavors_by_id.get(s.get("flavor_id", ""), {})
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
