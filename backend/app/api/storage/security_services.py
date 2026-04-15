import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
import openstack

from app.api.deps import get_os_conn
from app.models.storage import SecurityServiceInfo, CreateSecurityServiceRequest
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("", response_model=list[SecurityServiceInfo])
async def list_security_services(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"afterglow:manila:{pid}:security_services", ttl_fast(),
            lambda: manila.list_security_services(conn),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Security Service 목록 조회 실패")


@router.post("", response_model=SecurityServiceInfo, status_code=201)
@limiter.limit("10/minute")
async def create_security_service(
    request: Request,
    req: CreateSecurityServiceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(
            manila.create_security_service,
            conn, req.type, req.name, req.description,
            req.dns_ip, req.server, req.domain, req.user, req.password,
        )
        await invalidate(f"afterglow:manila:{pid}:security_services")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security Service 생성 실패: {e}")


@router.delete("/{security_service_id}", status_code=204)
async def delete_security_service(
    security_service_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(manila.delete_security_service, conn, security_service_id)
        await invalidate(f"afterglow:manila:{pid}:security_services")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security Service 삭제 실패: {e}")


@router.post("/{security_service_id}/attach", status_code=200)
async def attach_to_share_network(
    security_service_id: str,
    share_network_id: str = Query(...),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Security Service를 Share Network에 연결."""
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(
            manila.add_security_service_to_network, conn, share_network_id, security_service_id,
        )
        await invalidate(f"afterglow:manila:{pid}:share_networks")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security Service 연결 실패: {e}")


@router.delete("/{security_service_id}/detach", status_code=204)
async def detach_from_share_network(
    security_service_id: str,
    share_network_id: str = Query(...),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Security Service를 Share Network에서 해제."""
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(
            manila.remove_security_service_from_network, conn, share_network_id, security_service_id,
        )
        await invalidate(f"afterglow:manila:{pid}:share_networks")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Security Service 해제 실패: {e}")
