import asyncio
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn, get_token_info
from app.models.storage import ShareInfo
from app.services import manila, libraries as lib_svc
from app.config import get_settings


def _require_admin(token_info: dict = Depends(get_token_info)):
    """admin 역할이 없으면 403 반환."""
    roles = token_info.get("roles", [])
    if "admin" not in roles:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")

router = APIRouter()


@router.get("/shares", response_model=list[ShareInfo])
async def list_admin_shares(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """모든 Union 관련 share 목록 (prebuilt + dynamic)."""
    return manila.list_shares(conn)


@router.post("/shares/build", status_code=202)
async def trigger_build(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """
    사전 빌드 share 생성 트리거.
    실제 빌드는 별도 백그라운드 프로세스(scripts/build_library_shares.py)에서 수행.
    여기서는 빈 share를 생성하고 메타데이터만 기록한다.
    """
    settings = get_settings()
    try:
        lib = lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"알 수 없는 라이브러리: {library_id}")

    existing = manila.list_shares(conn, metadata_filter={
        "union_type": "prebuilt",
        "union_library": library_id,
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"이미 존재하는 사전 빌드 share: {existing[0].id}"
        )

    share = manila.create_share(
        conn,
        name=f"union-prebuilt-{library_id}",
        size_gb=20,
        share_network_id=settings.os_manila_share_network_id,
        share_type=settings.os_manila_share_type,
        metadata={
            "union_type": "prebuilt",
            "union_library": library_id,
            "union_version": lib.version,
            "union_status": "building",
        },
    )
    return {"share_id": share.id, "status": "building", "library": library_id}


# ---------------------------------------------------------------------------
# 관리자 전용 엔드포인트
# ---------------------------------------------------------------------------

@router.get("/overview", dependencies=[Depends(_require_admin)])
async def admin_overview(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """하이퍼바이저 및 전체 리소스 집계."""
    try:
        def _collect():
            hypervisors = list(conn.compute.hypervisors(details=True))
            total_vcpus = sum(getattr(h, 'vcpus', 0) or 0 for h in hypervisors)
            used_vcpus = sum(getattr(h, 'vcpus_used', 0) or 0 for h in hypervisors)
            total_ram = sum(getattr(h, 'memory_size', 0) or 0 for h in hypervisors)
            used_ram = sum(getattr(h, 'memory_used', 0) or 0 for h in hypervisors)
            total_disk = sum(getattr(h, 'local_disk_size', 0) or 0 for h in hypervisors)
            used_disk = sum(getattr(h, 'local_disk_used', 0) or 0 for h in hypervisors)
            return {
                "hypervisor_count": len(hypervisors),
                "vcpus": {"total": total_vcpus, "used": used_vcpus},
                "ram_gb": {"total": round(total_ram / 1024, 1), "used": round(used_ram / 1024, 1)},
                "disk_gb": {"total": total_disk, "used": used_disk},
            }
        return await asyncio.to_thread(_collect)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"개요 조회 실패: {e}")


@router.get("/hypervisors", dependencies=[Depends(_require_admin)])
async def list_hypervisors(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """컴퓨트 하이퍼바이저 목록."""
    try:
        def _list():
            return [
                {
                    "id": h.id,
                    "name": getattr(h, 'name', '') or getattr(h, 'hypervisor_hostname', ''),
                    "state": getattr(h, 'state', ''),
                    "status": getattr(h, 'status', ''),
                    "hypervisor_type": getattr(h, 'hypervisor_type', ''),
                    "vcpus": getattr(h, 'vcpus', 0),
                    "vcpus_used": getattr(h, 'vcpus_used', 0),
                    "memory_size_mb": getattr(h, 'memory_size', 0),
                    "memory_used_mb": getattr(h, 'memory_used', 0),
                    "local_disk_gb": getattr(h, 'local_disk_size', 0),
                    "local_disk_used_gb": getattr(h, 'local_disk_used', 0),
                    "running_vms": getattr(h, 'running_vms', 0),
                }
                for h in conn.compute.hypervisors(details=True)
            ]
        return await asyncio.to_thread(_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"하이퍼바이저 조회 실패: {e}")


@router.get("/all-instances", dependencies=[Depends(_require_admin)])
async def list_all_instances(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 인스턴스 목록."""
    try:
        def _list():
            return [
                {
                    "id": s.id,
                    "name": s.name or "",
                    "status": s.status or "",
                    "project_id": getattr(s, 'project_id', None),
                    "user_id": getattr(s, 'user_id', None),
                    "flavor": getattr(s, 'flavor', {}).get('original_name', '') if isinstance(getattr(s, 'flavor', None), dict) else '',
                    "created_at": str(s.created_at) if getattr(s, 'created_at', None) else None,
                }
                for s in conn.compute.servers(all_projects=True)
            ]
        return await asyncio.to_thread(_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 인스턴스 조회 실패: {e}")


@router.get("/all-volumes", dependencies=[Depends(_require_admin)])
async def list_all_volumes(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 볼륨 목록."""
    try:
        def _list():
            return [
                {
                    "id": v.id,
                    "name": v.name or "",
                    "status": v.status or "",
                    "size": v.size,
                    "project_id": getattr(v, 'project_id', None),
                    "created_at": str(v.created_at) if getattr(v, 'created_at', None) else None,
                }
                for v in conn.block_storage.volumes(details=True, all_projects=True)
            ]
        return await asyncio.to_thread(_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 볼륨 조회 실패: {e}")


@router.get("/quotas/{project_id}", dependencies=[Depends(_require_admin)])
async def get_quotas(project_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    """특정 프로젝트의 컴퓨트 쿼터 조회."""
    try:
        def _get():
            q = conn.compute.get_quota_set(project_id)
            return {
                "instances": {"limit": q.instances, "in_use": getattr(q, 'instances_used', 0)},
                "cores": {"limit": q.cores, "in_use": getattr(q, 'cores_used', 0)},
                "ram": {"limit": q.ram, "in_use": getattr(q, 'ram_used', 0)},
            }
        return await asyncio.to_thread(_get)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"쿼터 조회 실패: {e}")
