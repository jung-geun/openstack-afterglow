from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.common.activity_recorder import rec
from app.api.deps import get_os_conn, get_token_info
from app.models.storage import CreateShareNetworkRequest, ShareNetworkInfo
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.get("", response_model=list[ShareNetworkInfo])
async def list_share_networks(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:manila:{pid}:share_networks",
            ttl_fast(),
            lambda: manila.list_share_networks(conn),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Share 네트워크 목록 조회 실패")


@router.get("/{share_network_id}", response_model=ShareNetworkInfo)
async def get_share_network(
    share_network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(manila.get_share_network, conn, share_network_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Share 네트워크를 찾을 수 없습니다")


@router.post("", response_model=ShareNetworkInfo, status_code=201)
@limiter.limit("10/minute")
async def create_share_network(
    request: Request,
    req: CreateShareNetworkRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(
            manila.create_share_network,
            conn,
            req.name,
            req.neutron_net_id,
            req.neutron_subnet_id,
            req.description,
        )
        await invalidate(f"afterglow:manila:{pid}:share_networks")
        await rec(
            token_info,
            conn,
            resource_type="share_network",
            action="share_network.create",
            status="success",
            resource_name=req.name,
        )
        return result
    except Exception as e:
        _logger.warning("Share 네트워크 생성 실패: %s", e)
        await rec(
            token_info,
            conn,
            resource_type="share_network",
            action="share_network.create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Share 네트워크 생성 실패")


@router.delete("/{share_network_id}", status_code=204)
async def delete_share_network(
    share_network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(manila.delete_share_network, conn, share_network_id)
        await invalidate(f"afterglow:manila:{pid}:share_networks")
        await rec(
            token_info,
            conn,
            resource_type="share_network",
            action="share_network.delete",
            status="success",
            resource_id=share_network_id,
        )
    except Exception as e:
        _logger.warning("Share 네트워크 삭제 실패: %s", e)
        await rec(
            token_info,
            conn,
            resource_type="share_network",
            action="share_network.delete",
            status="failed",
            resource_id=share_network_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Share 네트워크 삭제 실패")
