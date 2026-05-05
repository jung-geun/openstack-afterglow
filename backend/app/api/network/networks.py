from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.deps import get_os_conn, get_token_info
from app.config import get_settings
from app.models.storage import (
    AssociateFipRequest,
    CreateFipRequest,
    CreateNetworkRequest,
    CreateSubnetRequest,
    FloatingIpInfo,
    NetworkDetail,
    NetworkInfo,
    SubnetDetail,
    TopologyData,
    TopologyInstance,
    UpdateSubnetRequest,
)
from app.rate_limit import limiter
from app.services import neutron, nova
from app.services.cache import cached_call, invalidate, ttl_fast, ttl_normal
from app.services.octavia import get_lb_stats, get_topology_lbs, lb_rate_from_snapshot, list_load_balancers
from app.services.prom_query import PromUnavailable, query_instant_multi

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[NetworkInfo])
async def list_networks(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:networks",
            ttl_normal(),
            lambda: neutron.list_networks(conn, pid),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="네트워크 목록 조회 실패")


@router.post("", response_model=NetworkInfo, status_code=201)
@limiter.limit("10/minute")
async def create_network(
    request: Request,
    req: CreateNetworkRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        result = await asyncio.to_thread(neutron.create_network, conn, req.name)
        await rec(token_info, conn, resource_type="network", action="create", resource_name=req.name)
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="network",
            action="create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="네트워크 생성 실패")


# ---------------------------------------------------------------------------
# Default 네트워크 (고정 경로 - /{network_id} 보다 먼저 등록)
# ---------------------------------------------------------------------------


class SetDefaultNetworkRequest(BaseModel):
    network_id: str


@router.post("/ensure-default", response_model=NetworkInfo, status_code=200)
@limiter.limit("10/minute")
async def ensure_default_network(
    request: Request,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """프로젝트의 Default 네트워크를 조회하거나 생성한다.

    프론트엔드에서 프로젝트 전환 시 호출 — DB에 이미 기록된 경우 빠르게 반환.
    """
    settings = get_settings()
    if not settings.default_network_enabled:
        raise HTTPException(status_code=404, detail="Default 네트워크 기능이 비활성화 상태입니다")
    project_id = conn._afterglow_project_id
    try:
        from app.services.default_network import ensure_default_network as _ensure

        net_info = await _ensure(
            conn,
            project_id,
            external_network_id=settings.default_network_external_id or None,
            cidr=settings.default_network_cidr,
        )
        # 네트워크 목록 캐시 무효화
        await invalidate(f"afterglow:neutron:{project_id}:networks")
        await rec(token_info, conn, resource_type="network", action="ensure_default", resource_id=net_info.id)
        return net_info
    except Exception:
        _logger.exception("Default 네트워크 ensure 실패")
        raise HTTPException(status_code=500, detail="Default 네트워크 처리 실패")


@router.get("/default", response_model=dict)
async def get_default_network(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """현재 프로젝트의 Default 네트워크 정보를 반환한다 (DB 기록 기준)."""
    project_id = conn._afterglow_project_id
    from app.services.default_network import get_default_network_record

    record = await get_default_network_record(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Default 네트워크가 설정되지 않았습니다")
    return record


@router.put("/default", response_model=dict)
async def set_default_network(
    req: SetDefaultNetworkRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """사용자가 원하는 네트워크를 프로젝트의 Default 네트워크로 지정한다."""
    project_id = conn._afterglow_project_id
    # 네트워크 존재 여부 확인
    try:
        net = await asyncio.to_thread(neutron.get_network, conn, req.network_id)
    except Exception:
        raise HTTPException(status_code=404, detail="네트워크를 찾을 수 없습니다")

    from app.services.default_network import get_default_network_record
    from app.services.default_network import set_default_network as _set

    # 서브넷 ID: 해당 네트워크의 첫 번째 서브넷 사용
    subnet_id = net.subnets[0] if net.subnets else None
    await _set(project_id, req.network_id, subnet_id)
    # 캐시 무효화
    await invalidate(f"afterglow:neutron:{project_id}:networks")
    record = await get_default_network_record(project_id)
    return record or {"project_id": project_id, "network_id": req.network_id}


# ---------------------------------------------------------------------------
# Floating IP (고정 경로 - /{network_id} 보다 먼저 등록)
# ---------------------------------------------------------------------------


@router.get("/floating-ips", response_model=list[FloatingIpInfo])
async def list_floating_ips(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:floating_ips",
            ttl_fast(),
            lambda: neutron.list_floating_ips(conn, pid),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Floating IP 목록 조회 실패")


@router.post("/floating-ips", response_model=FloatingIpInfo, status_code=201)
@limiter.limit("10/minute")
async def create_floating_ip(
    request: Request,
    req: CreateFipRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        result = await asyncio.to_thread(neutron.create_floating_ip, conn, req.floating_network_id)
        await rec(
            token_info,
            conn,
            resource_type="floating_ip",
            action="create",
            resource_id=result.id if hasattr(result, "id") else None,
        )
        return result
    except Exception as e:
        await rec(
            token_info, conn, resource_type="floating_ip", action="create", status="failed", error_message=str(e)[:500]
        )
        raise HTTPException(status_code=500, detail="Floating IP 생성 실패")


@router.post("/floating-ips/{fip_id}/associate", response_model=FloatingIpInfo)
@limiter.limit("10/minute")
async def associate_floating_ip(
    request: Request,
    fip_id: str,
    req: AssociateFipRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        result = await asyncio.to_thread(neutron.associate_floating_ip, conn, fip_id, req.instance_id)
        await rec(token_info, conn, resource_type="floating_ip", action="associate", resource_id=fip_id)
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="floating_ip",
            action="associate",
            status="failed",
            resource_id=fip_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Floating IP 연결 실패")


@router.post("/floating-ips/{fip_id}/disassociate", response_model=FloatingIpInfo)
@limiter.limit("10/minute")
async def disassociate_floating_ip(
    request: Request,
    fip_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(neutron.disassociate_floating_ip, conn, fip_id)
        await invalidate(f"afterglow:neutron:{pid}:floating_ips")
        await rec(token_info, conn, resource_type="floating_ip", action="disassociate", resource_id=fip_id)
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="floating_ip",
            action="disassociate",
            status="failed",
            resource_id=fip_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Floating IP 해제 실패")


@router.delete("/floating-ips/{fip_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_floating_ip(
    request: Request,
    fip_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(neutron.delete_floating_ip, conn, fip_id)
        await invalidate(f"afterglow:neutron:{pid}:floating_ips")
        await rec(token_info, conn, resource_type="floating_ip", action="delete", resource_id=fip_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="floating_ip",
            action="delete",
            status="failed",
            resource_id=fip_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="Floating IP 삭제 실패")


# ---------------------------------------------------------------------------
# 서브넷 (고정 경로)
# ---------------------------------------------------------------------------


@router.put("/subnets/{subnet_id}", response_model=SubnetDetail)
async def update_subnet(
    subnet_id: str,
    req: UpdateSubnetRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        result = await asyncio.to_thread(
            neutron.update_subnet, conn, subnet_id, req.name, req.gateway_ip, req.enable_dhcp
        )
        await rec(token_info, conn, resource_type="subnet", action="update", resource_id=subnet_id)
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="subnet",
            action="update",
            status="failed",
            resource_id=subnet_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="서브넷 업데이트 실패")


@router.delete("/subnets/{subnet_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_subnet(
    request: Request,
    subnet_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        await asyncio.to_thread(neutron.delete_subnet, conn, subnet_id)
        await rec(token_info, conn, resource_type="subnet", action="delete", resource_id=subnet_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="subnet",
            action="delete",
            status="failed",
            resource_id=subnet_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="서브넷 삭제 실패")


# ---------------------------------------------------------------------------
# 글로벌 토폴로지 (고정 경로 - 동적 경로보다 먼저 등록)
# ---------------------------------------------------------------------------


def _fetch_topology_sync(conn) -> dict:
    """동기 방식으로 토폴로지 전체 데이터 수집 (cached_call 내부에서 to_thread로 실행됨)."""
    topo = neutron.get_topology(conn)
    servers = nova.list_servers(conn)

    # Neutron 포트에서 (device_id, ip) → network_id 매핑 구축
    port_net_map: dict[tuple[str, str], str] = {}
    for p in conn.network.ports():
        dev_owner = p.device_owner or ""
        if not p.device_id or not dev_owner.startswith("compute:"):
            continue
        for fip in p.fixed_ips or []:
            ip = fip.get("ip_address")
            if ip:
                port_net_map[(p.device_id, ip)] = p.network_id

    instance_list = [
        TopologyInstance(
            id=s.id,
            name=s.name,
            status=s.status,
            project_id=s.project_id,
            network_names=list(set(ip.network_name for ip in s.ip_addresses)),
            ip_addresses=[
                {
                    **ip.model_dump(),
                    "network_id": port_net_map.get((s.id, ip.addr)),
                }
                for ip in s.ip_addresses
            ],
        )
        for s in servers
    ]
    topo.instances = instance_list
    topo.load_balancers = get_topology_lbs(
        conn,
        project_id=getattr(conn, "_afterglow_project_id", None),
        instances=[inst.model_dump() for inst in instance_list],
    )
    return topo.model_dump()


@router.get("/topology", response_model=TopologyData)
async def get_topology(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:topology",
            ttl_normal(),
            lambda: _fetch_topology_sync(conn),
            refresh=refresh,
        )
    except Exception:
        _logger.exception("토폴로지 조회 실패")
        raise HTTPException(status_code=500, detail="토폴로지 조회 실패")


@router.get("/topology/traffic")
async def get_topology_traffic(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """현재 토폴로지의 모든 리소스 instant 트래픽 (rx/tx bps).

    구조 엔드포인트(/topology)와 분리 — 15s 단주기 폴링 전용.
    반환: { ts, instances: {uuid: {rx_bps, tx_bps}}, networks, routers, load_balancers, _meta }
    """
    project_id = token_info.get("project_id", "") or conn._afterglow_project_id

    # 1) compute port 매핑 (Neutron 1회) — instance_ids + network→[instance_id]
    instance_ids, net_to_instances = await asyncio.to_thread(neutron.list_project_compute_ports, conn, project_id)

    # 2) PromQL instant queries — VM rx/tx 각 1회 (병렬)
    _exclude = r"lo|veth.*|docker.*|cni.*|tap.*|qbr.*"
    instances: dict[str, dict[str, float]] = {}
    if instance_ids:
        regex = "|".join(re.escape(i) for i in instance_ids)
        rx_q = (
            f"sum by (instance_id) (rate(node_network_receive_bytes_total"
            f'{{instance_id=~"{regex}",device!~"{_exclude}"}}[2m]))'
        )
        tx_q = rx_q.replace("receive", "transmit")
        try:
            rx_pairs, tx_pairs = await asyncio.gather(
                query_instant_multi(rx_q),
                query_instant_multi(tx_q),
            )
        except PromUnavailable:
            rx_pairs, tx_pairs = [], []
        for labels, val in rx_pairs:
            iid = labels.get("instance_id")
            if iid:
                instances.setdefault(iid, {"rx_bps": 0.0, "tx_bps": 0.0})["rx_bps"] = val * 8
        for labels, val in tx_pairs:
            iid = labels.get("instance_id")
            if iid:
                instances.setdefault(iid, {"rx_bps": 0.0, "tx_bps": 0.0})["tx_bps"] = val * 8

    # 3) 네트워크별 합산 — 백엔드에서 instance 결과 집계
    networks: dict[str, dict[str, float]] = {}
    for net_id, iids in net_to_instances.items():
        rx = sum(instances.get(i, {}).get("rx_bps", 0.0) for i in iids)
        tx = sum(instances.get(i, {}).get("tx_bps", 0.0) for i in iids)
        networks[net_id] = {"rx_bps": rx, "tx_bps": tx}

    # 4) LB stats — Octavia /stats 차분 (병렬)
    lbs = await asyncio.to_thread(list_load_balancers, conn, project_id)

    async def _lb_one(lb_id: str) -> tuple[str, dict[str, float]] | None:
        cur = await asyncio.to_thread(get_lb_stats, conn, lb_id)
        if cur is None:
            return None
        return lb_id, lb_rate_from_snapshot(lb_id, cur)

    lb_results = await asyncio.gather(*(_lb_one(lb["id"]) for lb in lbs))
    load_balancers = {lid: rate for lid, rate in (r for r in lb_results if r)}

    return {
        "ts": int(time.time()),
        "instances": instances,
        "networks": networks,
        "routers": {},  # Phase 2 — kolla ovs/libvirt exporter 활성화 후 채워짐
        "load_balancers": load_balancers,
        "_meta": {"router_traffic": "exporter_required"},
    }


# ---------------------------------------------------------------------------
# 포트 목록 (동적 경로보다 먼저 등록)
# ---------------------------------------------------------------------------


@router.get("/ports", response_model=list[dict])
async def list_ports(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """현재 프로젝트의 포트 목록."""
    project_id = conn._afterglow_project_id
    try:

        def _list():
            return [
                {
                    "id": p.id,
                    "name": p.name or "",
                    "status": p.status,
                    "mac_address": p.mac_address,
                    "fixed_ips": p.fixed_ips or [],
                    "network_id": p.network_id or "",
                    "device_owner": p.device_owner or "",
                    "device_id": p.device_id or "",
                }
                for p in conn.network.ports(project_id=project_id)
            ]

        return await asyncio.to_thread(_list)
    except Exception:
        _logger.exception("포트 목록 조회 실패")
        raise HTTPException(status_code=500, detail="포트 조회 실패")


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
@limiter.limit("10/minute")
async def delete_network(
    request: Request,
    network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        await asyncio.to_thread(neutron.delete_network, conn, network_id)
        await rec(token_info, conn, resource_type="network", action="delete", resource_id=network_id)
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="network",
            action="delete",
            status="failed",
            resource_id=network_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="네트워크 삭제 실패")


@router.post("/{network_id}/subnets", response_model=SubnetDetail, status_code=201)
@limiter.limit("10/minute")
async def create_subnet(
    request: Request,
    network_id: str,
    req: CreateSubnetRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        result = await asyncio.to_thread(
            neutron.create_subnet,
            conn,
            network_id,
            req.name,
            req.cidr,
            req.gateway_ip,
            req.enable_dhcp,
        )
        await rec(
            token_info,
            conn,
            resource_type="subnet",
            action="create",
            resource_name=req.name,
            resource_id=result.id if hasattr(result, "id") else None,
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="subnet",
            action="create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="서브넷 생성 실패")
