"""사용자별 크로스-프로젝트 대시보드 엔드포인트."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.services import keystone
from app.services.cache import cached_call

_logger = logging.getLogger(__name__)

router = APIRouter()


def _list_servers_for_project(conn: openstack.connection.Connection) -> list[dict]:
    return [
        {
            "id": s.id,
            "name": s.name or "",
            "status": s.status or "",
            "flavor_id": s.flavor_id or "",
            "flavor_name": s.flavor_name or "",
            "created_at": getattr(s, "created_at", None) or "",
        }
        for s in conn.compute.servers()
    ]


def _list_volumes_for_project(conn: openstack.connection.Connection) -> list[dict]:
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
    ]


async def _query_project(token: str, project_id: str, project_name: str) -> dict:
    """단일 프로젝트의 인스턴스/볼륨 정보를 비동기로 조회."""
    try:
        proj_conn = await asyncio.to_thread(
            keystone.get_openstack_connection, token, project_id
        )
        try:
            servers, volumes = await asyncio.gather(
                cached_call(
                    f"union:user-dashboard:{project_id}:servers", 30,
                    lambda c=proj_conn: _list_servers_for_project(c),
                ),
                cached_call(
                    f"union:user-dashboard:{project_id}:volumes", 30,
                    lambda c=proj_conn: _list_volumes_for_project(c),
                ),
            )
        finally:
            await asyncio.to_thread(proj_conn.close)

        total_vcpus = 0
        total_ram_mb = 0
        # 활성 인스턴스의 flavor 정보는 flavor_name만 있으므로 간단 집계 생략
        return {
            "project_id": project_id,
            "project_name": project_name,
            "instances": servers,
            "volumes": volumes,
            "instance_count": len(servers),
            "volume_count": len(volumes),
            "storage_gb": sum(v["size"] for v in volumes),
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
            "error": True,
        }


@router.get("/summary")
async def get_user_dashboard_summary(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """사용자가 소속된 모든 프로젝트의 인스턴스/볼륨 통합 조회."""
    token = conn._union_token
    current_project_id = conn._union_project_id

    try:
        projects = await asyncio.to_thread(keystone.list_projects, token)
    except Exception:
        raise HTTPException(status_code=500, detail="프로젝트 목록 조회 실패")

    # 병렬로 각 프로젝트 데이터 조회
    tasks = [
        _query_project(token, p["id"], p["name"])
        for p in projects
    ]
    project_results = await asyncio.gather(*tasks)

    totals = {
        "instances": sum(p["instance_count"] for p in project_results),
        "volumes": sum(p["volume_count"] for p in project_results),
        "storage_gb": sum(p["storage_gb"] for p in project_results),
    }

    return {
        "current_project_id": current_project_id,
        "projects": list(project_results),
        "totals": totals,
    }
