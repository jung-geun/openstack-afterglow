from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.common.activity_recorder import rec
from app.api.deps import CacheMode, cache_mode, get_os_conn, get_token_info
from app.models.storage import CreateSecurityServiceRequest, SecurityServiceInfo
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.get("", response_model=list[SecurityServiceInfo])
async def list_security_services(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:manila:{pid}:security_services",
            ttl_fast(),
            lambda: manila.list_security_services(conn),
            enabled=cm.enabled,
            refresh=cm.refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Security Service 목록 조회 실패")


@router.post("", response_model=SecurityServiceInfo, status_code=201)
@limiter.limit("10/minute")
async def create_security_service(
    request: Request,
    req: CreateSecurityServiceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(
            manila.create_security_service,
            conn,
            req.type,
            req.name,
            req.description,
            req.dns_ip,
            req.server,
            req.domain,
            req.user,
            req.password,
        )
        await invalidate(f"afterglow:manila:{pid}:security_services")
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.create",
            status="success",
            resource_name=req.name,
        )
        return result
    except Exception as e:
        _logger.warning("Security Service 생성 실패: %s", e)
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Security Service 생성 실패")


@router.delete("/{security_service_id}", status_code=204)
async def delete_security_service(
    security_service_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(manila.delete_security_service, conn, security_service_id)
        await invalidate(f"afterglow:manila:{pid}:security_services")
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.delete",
            status="success",
            resource_id=security_service_id,
        )
    except Exception as e:
        _logger.warning("Security Service 삭제 실패: %s", e)
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.delete",
            status="failed",
            resource_id=security_service_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Security Service 삭제 실패")


@router.post("/{security_service_id}/attach", status_code=200)
async def attach_to_share_network(
    security_service_id: str,
    share_network_id: str = Query(...),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """Security Service를 Share Network에 연결."""
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(
            manila.add_security_service_to_network,
            conn,
            share_network_id,
            security_service_id,
        )
        await invalidate(f"afterglow:manila:{pid}:share_networks")
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.attach",
            status="success",
            resource_id=security_service_id,
            extra={"share_network_id": share_network_id},
        )
        return result
    except Exception as e:
        _logger.warning("Security Service 연결 실패: %s", e)
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.attach",
            status="failed",
            resource_id=security_service_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Security Service 연결 실패")


@router.delete("/{security_service_id}/detach", status_code=204)
async def detach_from_share_network(
    security_service_id: str,
    share_network_id: str = Query(...),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """Security Service를 Share Network에서 해제."""
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(
            manila.remove_security_service_from_network,
            conn,
            share_network_id,
            security_service_id,
        )
        await invalidate(f"afterglow:manila:{pid}:share_networks")
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.detach",
            status="success",
            resource_id=security_service_id,
            extra={"share_network_id": share_network_id},
        )
    except Exception as e:
        _logger.warning("Security Service 해제 실패: %s", e)
        await rec(
            token_info,
            conn,
            resource_type="security_service",
            action="security_service.detach",
            status="failed",
            resource_id=security_service_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Security Service 해제 실패")
