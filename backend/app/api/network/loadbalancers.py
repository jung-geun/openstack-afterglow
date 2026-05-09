from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.common.owner_check import assert_resource_owner
from app.api.deps import get_os_conn, get_token_info
from app.rate_limit import limiter
from app.services import octavia
from app.services.cache import cached_call, invalidate, ttl_normal

router = APIRouter()


async def _assert_lb_owner(
    conn: openstack.connection.Connection,
    lb_id: str,
    token_info: dict,
):
    """LB owner 검증 — 모든 sub-resource(listener/pool/member/HM) 는 lb_id 가
    caller-owned 라면 간접적으로 보호된다."""
    try:
        lb = await asyncio.to_thread(conn.load_balancer.get_load_balancer, lb_id)
    except Exception:
        raise HTTPException(status_code=404, detail="로드밸런서를 찾을 수 없습니다")
    assert_resource_owner(lb, conn, token_info, not_found_detail="로드밸런서를 찾을 수 없습니다")


class CreateLbRequest(BaseModel):
    name: str
    vip_subnet_id: str
    description: str = ""


class CreateListenerRequest(BaseModel):
    protocol: str  # HTTP, HTTPS, TCP, UDP
    protocol_port: int
    name: str = ""
    default_pool_id: str | None = None


class CreatePoolRequest(BaseModel):
    protocol: str  # HTTP, HTTPS, TCP, UDP
    lb_algorithm: str = "ROUND_ROBIN"
    name: str = ""
    listener_id: str | None = None


class AddMemberRequest(BaseModel):
    address: str
    protocol_port: int
    subnet_id: str | None = None
    name: str = ""
    weight: int = 1


class CreateHealthMonitorRequest(BaseModel):
    type: str = "HTTP"  # HTTP, HTTPS, TCP, PING
    delay: int = 5
    timeout: int = 5
    max_retries: int = 3
    name: str = ""


def _handle(fn, error_msg: str):
    try:
        return fn()
    except Exception:
        raise HTTPException(status_code=500, detail=error_msg)


# ---------------------------------------------------------------------------
# Load Balancers
# ---------------------------------------------------------------------------


@router.get("")
async def list_load_balancers(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:octavia:{pid}:lbs",
            ttl_normal(),
            lambda: octavia.list_load_balancers(conn, project_id=pid),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="로드밸런서 목록 조회 실패")


@router.post("", status_code=201)
@limiter.limit("10/minute")
async def create_load_balancer(
    request: Request,
    req: CreateLbRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        result = octavia.create_load_balancer(conn, req.name, req.vip_subnet_id, req.description)
        await invalidate(f"afterglow:octavia:{pid}:lbs")
        await rec(token_info, conn, resource_type="load_balancer", action="create", resource_name=req.name)
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="load_balancer",
            action="create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="로드밸런서 생성 실패")


@router.get("/{lb_id}")
async def get_load_balancer(
    lb_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    return _handle(lambda: octavia.get_load_balancer(conn, lb_id), "로드밸런서 조회 실패")


@router.get("/{lb_id}/status")
async def get_lb_status_tree(
    lb_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    return _handle(lambda: octavia.get_lb_status_tree(conn, lb_id), "상태 트리 조회 실패")


@router.delete("/{lb_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_load_balancer(
    request: Request,
    lb_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        octavia.delete_load_balancer(conn, lb_id)
        await invalidate(f"afterglow:octavia:{pid}:lbs")
        await rec(token_info, conn, resource_type="load_balancer", action="delete", resource_id=lb_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="load_balancer",
            action="delete",
            status="failed",
            resource_id=lb_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="로드밸런서 삭제 실패")


# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------


@router.get("/{lb_id}/listeners")
async def list_listeners(
    lb_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    return _handle(lambda: octavia.list_listeners(conn, lb_id=lb_id), "리스너 목록 조회 실패")


@router.post("/{lb_id}/listeners", status_code=201)
@limiter.limit("10/minute")
async def create_listener(
    request: Request,
    lb_id: str,
    req: CreateListenerRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        result = octavia.create_listener(conn, lb_id, req.protocol, req.protocol_port, req.name, req.default_pool_id)
        await rec(
            token_info, conn, resource_type="lb_listener", action="create", resource_id=lb_id, resource_name=req.name
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_listener",
            action="create",
            status="failed",
            resource_id=lb_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="리스너 생성 실패")


@router.delete("/{lb_id}/listeners/{listener_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_listener(
    request: Request,
    lb_id: str,
    listener_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        octavia.delete_listener(conn, listener_id)
        await rec(token_info, conn, resource_type="lb_listener", action="delete", resource_id=listener_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_listener",
            action="delete",
            status="failed",
            resource_id=listener_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="리스너 삭제 실패")


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------


@router.get("/{lb_id}/pools")
async def list_pools(
    lb_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    return _handle(lambda: octavia.list_pools(conn, lb_id=lb_id), "풀 목록 조회 실패")


@router.post("/{lb_id}/pools", status_code=201)
@limiter.limit("10/minute")
async def create_pool(
    request: Request,
    lb_id: str,
    req: CreatePoolRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        result = octavia.create_pool(conn, lb_id, req.protocol, req.lb_algorithm, req.name, req.listener_id)
        await rec(token_info, conn, resource_type="lb_pool", action="create", resource_id=lb_id, resource_name=req.name)
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_pool",
            action="create",
            status="failed",
            resource_id=lb_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="풀 생성 실패")


@router.delete("/{lb_id}/pools/{pool_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_pool(
    request: Request,
    lb_id: str,
    pool_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        octavia.delete_pool(conn, pool_id)
        await rec(token_info, conn, resource_type="lb_pool", action="delete", resource_id=pool_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_pool",
            action="delete",
            status="failed",
            resource_id=pool_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="풀 삭제 실패")


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{lb_id}/pools/{pool_id}/members")
async def list_members(
    lb_id: str,
    pool_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    return _handle(lambda: octavia.list_members(conn, pool_id), "멤버 목록 조회 실패")


@router.post("/{lb_id}/pools/{pool_id}/members", status_code=201)
@limiter.limit("10/minute")
async def add_member(
    request: Request,
    lb_id: str,
    pool_id: str,
    req: AddMemberRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        result = octavia.add_member(conn, pool_id, req.address, req.protocol_port, req.subnet_id, req.name, req.weight)
        await rec(
            token_info, conn, resource_type="lb_member", action="create", resource_id=pool_id, resource_name=req.name
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_member",
            action="create",
            status="failed",
            resource_id=pool_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="멤버 추가 실패")


@router.delete("/{lb_id}/pools/{pool_id}/members/{member_id}", status_code=204)
@limiter.limit("10/minute")
async def remove_member(
    request: Request,
    lb_id: str,
    pool_id: str,
    member_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        octavia.remove_member(conn, pool_id, member_id)
        await rec(token_info, conn, resource_type="lb_member", action="delete", resource_id=member_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_member",
            action="delete",
            status="failed",
            resource_id=member_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="멤버 제거 실패")


# ---------------------------------------------------------------------------
# Health Monitors
# ---------------------------------------------------------------------------


@router.get("/{lb_id}/pools/{pool_id}/health-monitor")
async def list_health_monitors(
    lb_id: str,
    pool_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    return _handle(lambda: octavia.list_health_monitors(conn, pool_id=pool_id), "헬스모니터 조회 실패")


@router.post("/{lb_id}/pools/{pool_id}/health-monitor", status_code=201)
@limiter.limit("10/minute")
async def create_health_monitor(
    request: Request,
    lb_id: str,
    pool_id: str,
    req: CreateHealthMonitorRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        result = octavia.create_health_monitor(
            conn, pool_id, req.type, req.delay, req.timeout, req.max_retries, req.name
        )
        await rec(
            token_info,
            conn,
            resource_type="lb_health_monitor",
            action="create",
            resource_id=pool_id,
            resource_name=req.name,
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_health_monitor",
            action="create",
            status="failed",
            resource_id=pool_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="헬스모니터 생성 실패")


@router.delete("/{lb_id}/pools/{pool_id}/health-monitor/{hm_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_health_monitor(
    request: Request,
    lb_id: str,
    pool_id: str,
    hm_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_lb_owner(conn, lb_id, token_info)
    try:
        octavia.delete_health_monitor(conn, hm_id)
        await rec(token_info, conn, resource_type="lb_health_monitor", action="delete", resource_id=hm_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="lb_health_monitor",
            action="delete",
            status="failed",
            resource_id=hm_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="헬스모니터 삭제 실패")
