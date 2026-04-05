import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn, get_token_info

_logger = logging.getLogger(__name__)
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

def _fetch_hypervisors_raw(conn: openstack.connection.Connection) -> list[dict]:
    """Nova microversion 2.53으로 하이퍼바이저 raw JSON 조회.
    2.88+ 에서 vcpus/memory_mb 등 필드가 deprecated되므로 2.53을 명시적으로 사용."""
    endpoint = conn.compute.get_endpoint()
    resp = conn.session.get(
        f"{endpoint}/os-hypervisors/detail",
        headers={"OpenStack-API-Version": "compute 2.53"},
    )
    return resp.json().get("hypervisors", [])


@router.get("/overview", dependencies=[Depends(_require_admin)])
async def admin_overview(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """하이퍼바이저 및 전체 리소스 집계."""
    try:
        def _collect():
            data = _fetch_hypervisors_raw(conn)
            total_vcpus = sum(h.get("vcpus", 0) or 0 for h in data)
            used_vcpus = sum(h.get("vcpus_used", 0) or 0 for h in data)
            total_ram = sum(h.get("memory_mb", 0) or 0 for h in data)
            used_ram = sum(h.get("memory_mb_used", 0) or 0 for h in data)
            total_disk = sum(h.get("local_gb", 0) or 0 for h in data)
            used_disk = sum(h.get("local_gb_used", 0) or 0 for h in data)
            running_vms = sum(h.get("running_vms", 0) or 0 for h in data)

            # GPU 인스턴스: flavor 이름에 'gpu' 포함 여부로 집계
            gpu_instances = 0
            try:
                for s in conn.compute.servers(all_projects=True):
                    flavor = getattr(s, 'flavor', {}) or {}
                    fname = flavor.get('original_name', '') or ''
                    if 'gpu' in fname.lower():
                        gpu_instances += 1
            except Exception:
                pass

            return {
                "hypervisor_count": len(data),
                "running_vms": running_vms,
                "gpu_instances": gpu_instances,
                "vcpus": {"total": total_vcpus, "used": used_vcpus},
                "ram_gb": {"total": round(total_ram / 1024, 1), "used": round(used_ram / 1024, 1)},
                "disk_gb": {"total": total_disk, "used": used_disk},
            }
        return await asyncio.to_thread(_collect)
    except Exception as e:
        _logger.warning("admin overview 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail=f"개요 조회 실패: {e}")


@router.get("/hypervisors", dependencies=[Depends(_require_admin)])
async def list_hypervisors(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """컴퓨트 하이퍼바이저 목록."""
    try:
        def _list():
            data = _fetch_hypervisors_raw(conn)
            return [
                {
                    "id": h.get("id", ""),
                    "name": h.get("hypervisor_hostname", ""),
                    "state": h.get("state", ""),
                    "status": h.get("status", ""),
                    "hypervisor_type": h.get("hypervisor_type", ""),
                    "vcpus": h.get("vcpus", 0) or 0,
                    "vcpus_used": h.get("vcpus_used", 0) or 0,
                    "memory_size_mb": h.get("memory_mb", 0) or 0,
                    "memory_used_mb": h.get("memory_mb_used", 0) or 0,
                    "local_disk_gb": h.get("local_gb", 0) or 0,
                    "local_disk_used_gb": h.get("local_gb_used", 0) or 0,
                    "running_vms": h.get("running_vms", 0) or 0,
                }
                for h in data
            ]
        return await asyncio.to_thread(_list)
    except Exception as e:
        _logger.warning("hypervisors 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail=f"하이퍼바이저 조회 실패: {e}")


@router.get("/all-instances", dependencies=[Depends(_require_admin)])
async def list_all_instances(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """전체 프로젝트의 인스턴스 목록 (페이지네이션)."""
    try:
        def _list():
            kwargs: dict = {"all_projects": True, "limit": limit}
            if marker:
                kwargs["marker"] = marker
            items = [
                {
                    "id": s.id,
                    "name": s.name or "",
                    "status": s.status or "",
                    "project_id": getattr(s, 'project_id', None),
                    "user_id": getattr(s, 'user_id', None),
                    "flavor": getattr(s, 'flavor', {}).get('original_name', '') if isinstance(getattr(s, 'flavor', None), dict) else '',
                    "created_at": str(s.created_at) if getattr(s, 'created_at', None) else None,
                }
                for s in conn.compute.servers(**kwargs)
            ]
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}
        return await asyncio.to_thread(_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전체 인스턴스 조회 실패: {e}")


@router.get("/all-volumes", dependencies=[Depends(_require_admin)])
async def list_all_volumes(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """전체 프로젝트의 볼륨 목록 (페이지네이션)."""
    try:
        def _list():
            kwargs: dict = {"details": True, "all_projects": True, "limit": limit}
            if marker:
                kwargs["marker"] = marker
            items = [
                {
                    "id": v.id,
                    "name": v.name or "",
                    "status": v.status or "",
                    "size": v.size,
                    "project_id": getattr(v, 'project_id', None),
                    "created_at": str(v.created_at) if getattr(v, 'created_at', None) else None,
                }
                for v in conn.block_storage.volumes(**kwargs)
            ]
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}
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
