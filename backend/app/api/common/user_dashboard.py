"""사용자별 크로스-프로젝트 대시보드 엔드포인트."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn
from app.services import keystone
from app.services.cache import cached_call, ttl_normal, ttl_fast

_logger = logging.getLogger(__name__)

router = APIRouter()


def _list_servers_for_project(conn: openstack.connection.Connection, user_id: str) -> list[dict]:
    results = []
    for s in conn.compute.servers(user_id=user_id):
        flavor = getattr(s, "flavor", None) or {}
        if isinstance(flavor, dict):
            vcpus = flavor.get("vcpus", 0) or 0
            ram = flavor.get("ram", 0) or 0
            flavor_name = flavor.get("original_name") or flavor.get("name", "")
        else:
            vcpus = 0
            ram = 0
            flavor_name = getattr(s, "flavor_name", "") or ""
        results.append({
            "id": s.id,
            "name": s.name or "",
            "status": s.status or "",
            "flavor_name": flavor_name,
            "vcpus": vcpus,
            "ram_mb": ram,
            "created_at": getattr(s, "created_at", None) or "",
        })
    return results


def _list_volumes_for_project(conn: openstack.connection.Connection, user_id: str) -> list[dict]:
    return [
        {
            "id": v.id,
            "name": v.name or "",
            "status": v.status or "",
            "size": v.size or 0,
            "volume_type": v.volume_type or "",
            "created_at": getattr(v, "created_at", None) or "",
        }
        for v in conn.block_storage.volumes()
        if getattr(v, "user_id", None) == user_id
    ]


def _count_networks(conn: openstack.connection.Connection, project_id: str) -> int:
    return sum(
        1 for n in conn.network.networks()
        if getattr(n, "project_id", None) == project_id
    )


def _count_floating_ips(conn: openstack.connection.Connection, project_id: str) -> int:
    return sum(1 for _ in conn.network.ips(project_id=project_id))


async def _query_project(token: str, user_id: str, project_id: str, project_name: str, refresh: bool = False) -> dict:
    """단일 프로젝트의 인스턴스/볼륨/네트워크/FIP 정보를 비동기로 조회."""
    try:
        proj_conn = await asyncio.to_thread(
            keystone.get_openstack_connection, token, project_id
        )
        try:
            servers, volumes, network_count, fip_count = await asyncio.gather(
                cached_call(
                    f"afterglow:user-dashboard:{project_id}:{user_id}:servers", ttl_normal(),
                    lambda c=proj_conn, u=user_id: _list_servers_for_project(c, u),
                    refresh=refresh,
                ),
                cached_call(
                    f"afterglow:user-dashboard:{project_id}:{user_id}:volumes", ttl_normal(),
                    lambda c=proj_conn, u=user_id: _list_volumes_for_project(c, u),
                    refresh=refresh,
                ),
                cached_call(
                    f"afterglow:user-dashboard:{project_id}:networks", ttl_normal(),
                    lambda c=proj_conn, pid=project_id: _count_networks(c, pid),
                    refresh=refresh,
                ),
                cached_call(
                    f"afterglow:user-dashboard:{project_id}:fips", ttl_fast(),
                    lambda c=proj_conn, pid=project_id: _count_floating_ips(c, pid),
                    refresh=refresh,
                ),
            )
        finally:
            await asyncio.to_thread(proj_conn.close)

        total_vcpus = sum(s.get("vcpus", 0) for s in servers)
        total_ram_mb = sum(s.get("ram_mb", 0) for s in servers)

        return {
            "project_id": project_id,
            "project_name": project_name,
            "instances": servers,
            "volumes": volumes,
            "instance_count": len(servers),
            "volume_count": len(volumes),
            "storage_gb": sum(v["size"] for v in volumes),
            "vcpus": total_vcpus,
            "ram_mb": total_ram_mb,
            "network_count": network_count,
            "fip_count": fip_count,
        }
    except Exception:
        _logger.warning("프로젝트 %s 데이터 조회 실패", project_id, exc_info=True)
        return {
            "project_id": project_id,
            "project_name": project_name,
            "instances": [],
            "volumes": [],
            "instance_count": 0,
            "volume_count": 0,
            "storage_gb": 0,
            "vcpus": 0,
            "ram_mb": 0,
            "network_count": 0,
            "fip_count": 0,
            "error": True,
        }


@router.get("/summary")
async def get_user_dashboard_summary(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
):
    """사용자가 소속된 모든 프로젝트의 인스턴스/볼륨 통합 조회."""
    token = conn._union_token
    current_project_id = conn._union_project_id
    user_id = conn._union_user_id

    try:
        projects = await asyncio.to_thread(keystone.list_projects, token)
    except Exception:
        raise HTTPException(status_code=500, detail="프로젝트 목록 조회 실패")

    # 병렬로 각 프로젝트 데이터 조회
    tasks = [
        _query_project(token, user_id, p["id"], p["name"], refresh=refresh)
        for p in projects
    ]
    project_results = await asyncio.gather(*tasks)

    totals = {
        "instances": sum(p["instance_count"] for p in project_results),
        "volumes": sum(p["volume_count"] for p in project_results),
        "storage_gb": sum(p["storage_gb"] for p in project_results),
        "vcpus": sum(p["vcpus"] for p in project_results),
        "ram_mb": sum(p["ram_mb"] for p in project_results),
        "networks": sum(p["network_count"] for p in project_results),
        "floating_ips": sum(p["fip_count"] for p in project_results),
    }

    return {
        "current_project_id": current_project_id,
        "projects": list(project_results),
        "totals": totals,
    }
