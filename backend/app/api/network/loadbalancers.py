from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import openstack

from app.api.deps import get_os_conn
from app.services import octavia
from app.services.cache import cached_call, invalidate, ttl_normal

router = APIRouter()


class CreateLbRequest(BaseModel):
    name: str
    vip_subnet_id: str
    description: str = ""


class CreateListenerRequest(BaseModel):
    protocol: str           # HTTP, HTTPS, TCP, UDP
    protocol_port: int
    name: str = ""
    default_pool_id: Optional[str] = None


class CreatePoolRequest(BaseModel):
    protocol: str           # HTTP, HTTPS, TCP, UDP
    lb_algorithm: str = "ROUND_ROBIN"
    name: str = ""
    listener_id: Optional[str] = None


class AddMemberRequest(BaseModel):
    address: str
    protocol_port: int
    subnet_id: Optional[str] = None
    name: str = ""
    weight: int = 1


class CreateHealthMonitorRequest(BaseModel):
    type: str = "HTTP"      # HTTP, HTTPS, TCP, PING
    delay: int = 5
    timeout: int = 5
    max_retries: int = 3
    name: str = ""


def _handle(fn, error_msg: str):
    try:
        return fn()
    except Exception as e:
        raise HTTPException(status_code=500, detail=error_msg)


# ---------------------------------------------------------------------------
# Load Balancers
# ---------------------------------------------------------------------------

@router.get("")
async def list_load_balancers(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:octavia:{pid}:lbs", ttl_normal(),
            lambda: octavia.list_load_balancers(conn, project_id=pid),
            refresh=refresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="로드밸런서 목록 조회 실패")


@router.post("", status_code=201)
async def create_load_balancer(
    req: CreateLbRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = octavia.create_load_balancer(conn, req.name, req.vip_subnet_id, req.description)
        await invalidate(f"union:octavia:{pid}:lbs")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="로드밸런서 생성 실패")


@router.get("/{lb_id}")
async def get_load_balancer(lb_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    return _handle(lambda: octavia.get_load_balancer(conn, lb_id), "로드밸런서 조회 실패")


@router.get("/{lb_id}/status")
async def get_lb_status_tree(lb_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    return _handle(lambda: octavia.get_lb_status_tree(conn, lb_id), "상태 트리 조회 실패")


@router.delete("/{lb_id}", status_code=204)
async def delete_load_balancer(lb_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    pid = conn._union_project_id
    _handle(lambda: octavia.delete_load_balancer(conn, lb_id), "로드밸런서 삭제 실패")
    await invalidate(f"union:octavia:{pid}:lbs")


# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------

@router.get("/{lb_id}/listeners")
async def list_listeners(lb_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    return _handle(lambda: octavia.list_listeners(conn, lb_id=lb_id), "리스너 목록 조회 실패")


@router.post("/{lb_id}/listeners", status_code=201)
async def create_listener(
    lb_id: str,
    req: CreateListenerRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    return _handle(
        lambda: octavia.create_listener(conn, lb_id, req.protocol, req.protocol_port, req.name, req.default_pool_id),
        "리스너 생성 실패",
    )


@router.delete("/{lb_id}/listeners/{listener_id}", status_code=204)
async def delete_listener(lb_id: str, listener_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    _handle(lambda: octavia.delete_listener(conn, listener_id), "리스너 삭제 실패")


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------

@router.get("/{lb_id}/pools")
async def list_pools(lb_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    return _handle(lambda: octavia.list_pools(conn, lb_id=lb_id), "풀 목록 조회 실패")


@router.post("/{lb_id}/pools", status_code=201)
async def create_pool(
    lb_id: str,
    req: CreatePoolRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    return _handle(
        lambda: octavia.create_pool(conn, lb_id, req.protocol, req.lb_algorithm, req.name, req.listener_id),
        "풀 생성 실패",
    )


@router.delete("/{lb_id}/pools/{pool_id}", status_code=204)
async def delete_pool(lb_id: str, pool_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    _handle(lambda: octavia.delete_pool(conn, pool_id), "풀 삭제 실패")


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@router.get("/{lb_id}/pools/{pool_id}/members")
async def list_members(lb_id: str, pool_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    return _handle(lambda: octavia.list_members(conn, pool_id), "멤버 목록 조회 실패")


@router.post("/{lb_id}/pools/{pool_id}/members", status_code=201)
async def add_member(
    lb_id: str,
    pool_id: str,
    req: AddMemberRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    return _handle(
        lambda: octavia.add_member(conn, pool_id, req.address, req.protocol_port, req.subnet_id, req.name, req.weight),
        "멤버 추가 실패",
    )


@router.delete("/{lb_id}/pools/{pool_id}/members/{member_id}", status_code=204)
async def remove_member(
    lb_id: str, pool_id: str, member_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    _handle(lambda: octavia.remove_member(conn, pool_id, member_id), "멤버 제거 실패")


# ---------------------------------------------------------------------------
# Health Monitors
# ---------------------------------------------------------------------------

@router.get("/{lb_id}/pools/{pool_id}/health-monitor")
async def list_health_monitors(lb_id: str, pool_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    return _handle(lambda: octavia.list_health_monitors(conn, pool_id=pool_id), "헬스모니터 조회 실패")


@router.post("/{lb_id}/pools/{pool_id}/health-monitor", status_code=201)
async def create_health_monitor(
    lb_id: str,
    pool_id: str,
    req: CreateHealthMonitorRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    return _handle(
        lambda: octavia.create_health_monitor(conn, pool_id, req.type, req.delay, req.timeout, req.max_retries, req.name),
        "헬스모니터 생성 실패",
    )


@router.delete("/{lb_id}/pools/{pool_id}/health-monitor/{hm_id}", status_code=204)
async def delete_health_monitor(
    lb_id: str, pool_id: str, hm_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    _handle(lambda: octavia.delete_health_monitor(conn, hm_id), "헬스모니터 삭제 실패")
