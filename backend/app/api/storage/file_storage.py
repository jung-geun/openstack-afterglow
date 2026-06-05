from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.common.activity_recorder import rec
from app.api.deps import CacheMode, cache_mode, get_os_conn, get_token_info
from app.config import get_settings
from app.models.storage import CreateAccessRuleRequest, CreateFileStorageRequest, FileStorageInfo
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast
from app.services.manila import _build_nfs_access_metadata, extract_manila_error

router = APIRouter()
_logger = logging.getLogger(__name__)


def _assert_share_owner(share, conn, token_info: dict) -> None:
    """Manila share owner 검증 — afterglow 가 union_project_id metadata 로 owner 추적.

    admin 우회 + is_public share 는 cross-project 정상 노출이라 면제.
    """
    if token_info.get("is_system_admin", False):
        return
    pid = getattr(conn, "_afterglow_project_id", None)
    owner = (share.metadata or {}).get("union_project_id", "")
    if owner and owner != pid and not getattr(share, "is_public", False):
        raise HTTPException(status_code=404, detail="파일 스토리지를 찾을 수 없습니다")


def _fetch_and_assert_share_owner(conn, file_storage_id: str, token_info: dict):
    try:
        share = manila.get_file_storage(conn, file_storage_id)
    except Exception:
        raise HTTPException(status_code=404, detail="파일 스토리지를 찾을 수 없습니다")
    _assert_share_owner(share, conn, token_info)
    return share


@router.get("/quota")
async def get_file_storage_quota(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_file_storage_quota(conn)
    except Exception:
        raise HTTPException(status_code=500, detail="파일 스토리지 쿼터 조회 실패")


@router.get("", response_model=list[FileStorageInfo])
async def list_file_storages(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
    cm: CacheMode = Depends(cache_mode),
):
    pid = conn._afterglow_project_id
    is_admin = token_info.get("is_system_admin", False)
    caller_project_id = None if is_admin else pid
    try:
        return await cached_call(
            f"afterglow:manila:{pid}:file_storages",
            ttl_fast(),
            lambda: [s.model_dump() for s in manila.list_file_storages(conn, caller_project_id=caller_project_id)],
            enabled=cm.enabled,
            refresh=cm.refresh,
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
async def get_file_storage(
    file_storage_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    return _fetch_and_assert_share_owner(conn, file_storage_id, token_info)


@router.post("", response_model=FileStorageInfo, status_code=201)
@limiter.limit("5/minute")
async def create_file_storage(
    request: Request,
    req: CreateFileStorageRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
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
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.create",
            status="success",
            resource_name=req.name,
            extra={"size_gb": req.size_gb},
        )
        return result
    except httpx.HTTPStatusError as e:
        # Manila API 가 4xx/5xx 응답을 준 경우 — status code 와 detail 메시지를 그대로 전달
        status, message = extract_manila_error(e)
        _logger.warning("Manila %s on share create: %s", status, message[:300])
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.create",
            status="failed",
            resource_name=req.name,
            error_message=message[:500],
        )
        # 4xx 는 그대로, 5xx 는 외부 서비스 장애로 표현
        raise HTTPException(
            status_code=status if 400 <= status < 500 else 502,
            detail=message,
        )
    except Exception as e:
        _logger.exception("파일 스토리지 생성 실패: name=%s proto=%s", req.name, req.share_proto)
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail=f"파일 스토리지 생성 실패: {str(e)[:200]}")


@router.delete("/{file_storage_id}", status_code=204)
async def delete_file_storage(
    file_storage_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    _fetch_and_assert_share_owner(conn, file_storage_id, token_info)
    try:
        manila.delete_file_storage(conn, file_storage_id)
        await invalidate(f"afterglow:manila:{pid}:file_storages")
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.delete",
            status="success",
            resource_id=file_storage_id,
        )
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.delete",
            status="failed",
            resource_id=file_storage_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="파일 스토리지 삭제 실패")


# ---------------------------------------------------------------------------
# Access Rules
# ---------------------------------------------------------------------------


@router.get("/{file_storage_id}/access-rules")
async def list_access_rules(
    file_storage_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    _fetch_and_assert_share_owner(conn, file_storage_id, token_info)
    try:
        return manila.list_access_rules(conn, file_storage_id)
    except Exception:
        raise HTTPException(status_code=500, detail="접근 규칙 목록 조회 실패")


@router.post("/{file_storage_id}/access-rules", status_code=201)
async def create_access_rule(
    file_storage_id: str,
    req: CreateAccessRuleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    _fetch_and_assert_share_owner(conn, file_storage_id, token_info)
    try:
        metadata = _build_nfs_access_metadata(req.root_squash, req.sec_flavor) if req.access_type == "ip" else None
        result = manila.create_access_rule(
            conn, file_storage_id, req.access_to, req.access_level, req.access_type, metadata=metadata
        )
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.grant_access",
            status="success",
            resource_id=file_storage_id,
            extra={"access_to": req.access_to},
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.grant_access",
            status="failed",
            resource_id=file_storage_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="접근 규칙 생성 실패")


@router.delete("/{file_storage_id}/access-rules/{access_id}", status_code=204)
async def revoke_access_rule(
    file_storage_id: str,
    access_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    _fetch_and_assert_share_owner(conn, file_storage_id, token_info)
    try:
        manila.revoke_access_rule(conn, file_storage_id, access_id)
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.revoke_access",
            status="success",
            resource_id=file_storage_id,
        )
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="file_storage",
            action="file_storage.revoke_access",
            status="failed",
            resource_id=file_storage_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="접근 규칙 삭제 실패")
