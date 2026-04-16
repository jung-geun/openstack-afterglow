import openstack
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_os_conn
from app.services import neutron
from app.services.cache import cached_call, invalidate, ttl_slow

router = APIRouter()


class CreateSecurityGroupRequest(BaseModel):
    name: str
    description: str = ""


class CreateSecurityGroupRuleRequest(BaseModel):
    direction: str  # "ingress" | "egress"
    protocol: str | None = None  # "tcp", "udp", "icmp", None (any)
    port_range_min: int | None = None
    port_range_max: int | None = None
    remote_ip_prefix: str | None = None
    ethertype: str = "IPv4"


@router.get("")
async def list_security_groups(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:security_groups",
            ttl_slow(),
            lambda: neutron.list_security_groups(conn, project_id=pid),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="보안 그룹 목록 조회 실패")


@router.post("", status_code=201)
async def create_security_group(
    req: CreateSecurityGroupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = neutron.create_security_group(conn, req.name, req.description)
        await invalidate(f"afterglow:neutron:{pid}:security_groups")
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="보안 그룹 생성 실패")


@router.delete("/{sg_id}", status_code=204)
async def delete_security_group(
    sg_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        neutron.delete_security_group(conn, sg_id)
        await invalidate(f"afterglow:neutron:{pid}:security_groups")
    except Exception:
        raise HTTPException(status_code=500, detail="보안 그룹 삭제 실패")


@router.post("/{sg_id}/rules", status_code=201)
async def create_security_group_rule(
    sg_id: str,
    req: CreateSecurityGroupRuleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = neutron.create_security_group_rule(
            conn,
            sg_id=sg_id,
            direction=req.direction,
            protocol=req.protocol,
            port_range_min=req.port_range_min,
            port_range_max=req.port_range_max,
            remote_ip_prefix=req.remote_ip_prefix,
            ethertype=req.ethertype,
        )
        await invalidate(f"afterglow:neutron:{pid}:security_groups")
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="보안 그룹 규칙 추가 실패")


@router.delete("/{sg_id}/rules/{rule_id}", status_code=204)
async def delete_security_group_rule(
    sg_id: str,
    rule_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        neutron.delete_security_group_rule(conn, rule_id)
        await invalidate(f"afterglow:neutron:{pid}:security_groups")
    except Exception:
        raise HTTPException(status_code=500, detail="보안 그룹 규칙 삭제 실패")
