import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn
from app.models.storage import (
    RouterInfo, RouterDetail,
    CreateRouterRequest, RouterInterfaceRequest, RouterGatewayRequest,
)
from app.services import neutron
from app.services.cache import cached_call, invalidate, ttl_normal

router = APIRouter()


@router.get("", response_model=list[RouterInfo])
async def list_routers(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:routers", ttl_normal(),
            lambda: [r.model_dump() for r in neutron.list_routers(conn, project_id=pid)],
            refresh=refresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="라우터 목록 조회 실패")


@router.post("", response_model=RouterInfo, status_code=201)
async def create_router(
    req: CreateRouterRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(neutron.create_router, conn, req.name, req.external_network_id)
        await invalidate(f"afterglow:neutron:{pid}:routers")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="라우터 생성 실패")


@router.get("/{router_id}", response_model=RouterDetail)
async def get_router(router_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(neutron.get_router_detail, conn, router_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="라우터 조회 실패")


@router.delete("/{router_id}", status_code=204)
async def delete_router(router_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(neutron.delete_router, conn, router_id)
        await invalidate(f"afterglow:neutron:{pid}:routers")
    except Exception as e:
        raise HTTPException(status_code=500, detail="라우터 삭제 실패")


@router.post("/{router_id}/interfaces", status_code=201)
async def add_interface(
    router_id: str,
    req: RouterInterfaceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(neutron.add_router_interface, conn, router_id, req.subnet_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="인터페이스 추가 실패")


@router.delete("/{router_id}/interfaces/{subnet_id}", status_code=204)
async def remove_interface(
    router_id: str,
    subnet_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(neutron.remove_router_interface, conn, router_id, subnet_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="인터페이스 제거 실패")


@router.post("/{router_id}/gateway", status_code=204)
async def set_gateway(
    router_id: str,
    req: RouterGatewayRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(neutron.set_router_gateway, conn, router_id, req.external_network_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="게이트웨이 설정 실패")


@router.delete("/{router_id}/gateway", status_code=204)
async def remove_gateway(
    router_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(neutron.remove_router_gateway, conn, router_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="게이트웨이 제거 실패")
