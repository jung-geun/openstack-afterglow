import openstack
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_os_conn
from app.config import get_settings
from app.models.storage import CreateAccessRuleRequest, CreateFileStorageRequest, FileStorageInfo
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("/quota")
async def get_file_storage_quota(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_file_storage_quota(conn)
    except Exception:
        raise HTTPException(status_code=500, detail="파일 스토리지 쿼터 조회 실패")


@router.get("", response_model=list[FileStorageInfo])
async def list_file_storages(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:manila:{pid}:file_storages",
            ttl_fast(),
            lambda: [s.model_dump() for s in manila.list_file_storages(conn)],
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="파일 스토리지 목록 조회 실패")


@router.get("/types")
async def list_share_types(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.list_share_types(conn)
    except Exception:
        raise HTTPException(status_code=500, detail="Share 타입 목록 조회 실패")


@router.get("/networks")
async def list_share_networks(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.list_share_networks(conn)
    except Exception:
        raise HTTPException(status_code=500, detail="Share 네트워크 목록 조회 실패")


@router.get("/{file_storage_id}", response_model=FileStorageInfo)
async def get_file_storage(file_storage_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_file_storage(conn, file_storage_id)
    except Exception:
        raise HTTPException(status_code=404, detail="파일 스토리지를 찾을 수 없습니다")


@router.post("", response_model=FileStorageInfo, status_code=201)
@limiter.limit("5/minute")
async def create_file_storage(
    request: Request,
    req: CreateFileStorageRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._afterglow_project_id
    try:
        settings = get_settings()
        result = manila.create_file_storage(
            conn,
            name=req.name,
            size_gb=req.size_gb,
            share_network_id=req.share_network_id or settings.os_manila_share_network_id,
            share_type=req.share_type or settings.os_manila_share_type,
            share_proto=req.share_proto,
            metadata=req.metadata,
        )
        await invalidate(f"afterglow:manila:{pid}:file_storages")
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="파일 스토리지 생성 실패")


@router.delete("/{file_storage_id}", status_code=204)
async def delete_file_storage(
    file_storage_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._afterglow_project_id
    try:
        manila.delete_file_storage(conn, file_storage_id)
        await invalidate(f"afterglow:manila:{pid}:file_storages")
    except Exception:
        raise HTTPException(status_code=500, detail="파일 스토리지 삭제 실패")


# ---------------------------------------------------------------------------
# Access Rules
# ---------------------------------------------------------------------------


@router.get("/{file_storage_id}/access-rules")
async def list_access_rules(file_storage_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.list_access_rules(conn, file_storage_id)
    except Exception:
        raise HTTPException(status_code=500, detail="접근 규칙 목록 조회 실패")


@router.post("/{file_storage_id}/access-rules", status_code=201)
async def create_access_rule(
    file_storage_id: str,
    req: CreateAccessRuleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return manila.create_access_rule(conn, file_storage_id, req.access_to, req.access_level, req.access_type)
    except Exception:
        raise HTTPException(status_code=500, detail="접근 규칙 생성 실패")


@router.delete("/{file_storage_id}/access-rules/{access_id}", status_code=204)
async def revoke_access_rule(
    file_storage_id: str,
    access_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        manila.revoke_access_rule(conn, file_storage_id, access_id)
    except Exception:
        raise HTTPException(status_code=500, detail="접근 규칙 삭제 실패")
