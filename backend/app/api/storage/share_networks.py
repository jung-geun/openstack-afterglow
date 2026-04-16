import asyncio

import openstack
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_os_conn
from app.models.storage import CreateShareNetworkRequest, ShareNetworkInfo
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("", response_model=list[ShareNetworkInfo])
async def list_share_networks(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
):
    pid = conn._union_project_id
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
):
    pid = conn._union_project_id
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
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Share 네트워크 생성 실패: {e}")


@router.delete("/{share_network_id}", status_code=204)
async def delete_share_network(
    share_network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(manila.delete_share_network, conn, share_network_id)
        await invalidate(f"afterglow:manila:{pid}:share_networks")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Share 네트워크 삭제 실패: {e}")
