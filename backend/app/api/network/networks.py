import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn
from app.models.storage import (
    NetworkInfo, NetworkDetail, SubnetDetail,
    CreateNetworkRequest, CreateSubnetRequest,
    FloatingIpInfo, CreateFipRequest, AssociateFipRequest,
    TopologyData, TopologyInstance,
)
from app.services import neutron, nova
from app.services.cache import cached_call, ttl_fast, ttl_normal

router = APIRouter()


@router.get("", response_model=list[NetworkInfo])
async def list_networks(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:neutron:{pid}:networks", ttl_normal(),
            lambda: neutron.list_networks(conn, pid),
            refresh=refresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="네트워크 목록 조회 실패")


@router.post("", response_model=NetworkInfo, status_code=201)
async def create_network(
    req: CreateNetworkRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(neutron.create_network, conn, req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail="네트워크 생성 실패")


# ---------------------------------------------------------------------------
# Floating IP (고정 경로 - /{network_id} 보다 먼저 등록)
# ---------------------------------------------------------------------------

@router.get("/floating-ips", response_model=list[FloatingIpInfo])
async def list_floating_ips(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:neutron:{pid}:floating_ips", ttl_fast(),
            lambda: neutron.list_floating_ips(conn, pid),
            refresh=refresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Floating IP 목록 조회 실패")


@router.post("/floating-ips", response_model=FloatingIpInfo, status_code=201)
async def create_floating_ip(
    req: CreateFipRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(neutron.create_floating_ip, conn, req.floating_network_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Floating IP 생성 실패")


@router.post("/floating-ips/{fip_id}/associate", response_model=FloatingIpInfo)
async def associate_floating_ip(
    fip_id: str,
    req: AssociateFipRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(neutron.associate_floating_ip, conn, fip_id, req.instance_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Floating IP 연결 실패")


@router.post("/floating-ips/{fip_id}/disassociate", response_model=FloatingIpInfo)
async def disassociate_floating_ip(
    fip_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(neutron.disassociate_floating_ip, conn, fip_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Floating IP 해제 실패")


@router.delete("/floating-ips/{fip_id}", status_code=204)
async def delete_floating_ip(
    fip_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(neutron.delete_floating_ip, conn, fip_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Floating IP 삭제 실패")


# ---------------------------------------------------------------------------
# 서브넷 (고정 경로)
# ---------------------------------------------------------------------------

@router.delete("/subnets/{subnet_id}", status_code=204)
async def delete_subnet(
    subnet_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(neutron.delete_subnet, conn, subnet_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="서브넷 삭제 실패")


# ---------------------------------------------------------------------------
# 글로벌 토폴로지 (고정 경로 - 동적 경로보다 먼저 등록)
# ---------------------------------------------------------------------------

def _fetch_topology_sync(conn) -> dict:
    """동기 방식으로 토폴로지 전체 데이터 수집 (cached_call 내부에서 to_thread로 실행됨)."""
    topo = neutron.get_topology(conn)
    servers = nova.list_servers(conn)
    topo.instances = [
        TopologyInstance(
            id=s.id,
            name=s.name,
            status=s.status,
            network_names=list(set(ip.network_name for ip in s.ip_addresses)),
            ip_addresses=[ip.model_dump() for ip in s.ip_addresses],
        )
        for s in servers
    ]
    return topo.model_dump()


@router.get("/topology", response_model=TopologyData)
async def get_topology(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:neutron:{pid}:topology", ttl_normal(),
            lambda: _fetch_topology_sync(conn),
            refresh=refresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="토폴로지 조회 실패")


# ---------------------------------------------------------------------------
# 네트워크 상세 (동적 경로 - 마지막에 등록)
# ---------------------------------------------------------------------------

@router.get("/{network_id}", response_model=NetworkDetail)
async def get_network(network_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(neutron.get_network_detail, conn, network_id)
    except Exception:
        raise HTTPException(status_code=404, detail="네트워크를 찾을 수 없습니다")


@router.delete("/{network_id}", status_code=204)
async def delete_network(
    network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(neutron.delete_network, conn, network_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="네트워크 삭제 실패")


@router.post("/{network_id}/subnets", response_model=SubnetDetail, status_code=201)
async def create_subnet(
    network_id: str,
    req: CreateSubnetRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(
            neutron.create_subnet,
            conn, network_id, req.name, req.cidr,
            req.gateway_ip, req.enable_dhcp,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="서브넷 생성 실패")
