from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.common.owner_check import assert_resource_owner
from app.api.deps import CacheMode, cache_mode, get_os_conn, get_token_info
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
from app.services.cache import cached_call, invalidate, ttl_fast, ttl_normal, ttl_static
from app.services.octavia import get_lb_stats, get_topology_lbs, lb_rate_from_snapshot, list_load_balancers
from app.services.prom_query import PromBadQuery, PromUnavailable, query_instant_multi

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[NetworkInfo])
async def list_networks(
    conn: openstack.connection.Connection = Depends(get_os_conn), cm: CacheMode = Depends(cache_mode)
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:networks",
            ttl_normal(),
            lambda: neutron.list_networks(conn, pid),
            enabled=cm.enabled,
            refresh=cm.refresh,
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
async def list_floating_ips(
    conn: openstack.connection.Connection = Depends(get_os_conn), cm: CacheMode = Depends(cache_mode)
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:floating_ips",
            ttl_fast(),
            lambda: neutron.list_floating_ips(conn, pid),
            enabled=cm.enabled,
            refresh=cm.refresh,
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
        fip = await asyncio.to_thread(conn.network.get_ip, fip_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Floating IP를 찾을 수 없습니다")
    assert_resource_owner(fip, conn, token_info, not_found_detail="Floating IP를 찾을 수 없습니다")
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
        fip = await asyncio.to_thread(conn.network.get_ip, fip_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Floating IP를 찾을 수 없습니다")
    assert_resource_owner(fip, conn, token_info, not_found_detail="Floating IP를 찾을 수 없습니다")
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
        fip = await asyncio.to_thread(conn.network.get_ip, fip_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Floating IP를 찾을 수 없습니다")
    assert_resource_owner(fip, conn, token_info, not_found_detail="Floating IP를 찾을 수 없습니다")
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
        sub = await asyncio.to_thread(conn.network.get_subnet, subnet_id)
    except Exception:
        raise HTTPException(status_code=404, detail="서브넷을 찾을 수 없습니다")
    assert_resource_owner(sub, conn, token_info, not_found_detail="서브넷을 찾을 수 없습니다")
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
        sub = await asyncio.to_thread(conn.network.get_subnet, subnet_id)
    except Exception:
        raise HTTPException(status_code=404, detail="서브넷을 찾을 수 없습니다")
    assert_resource_owner(sub, conn, token_info, not_found_detail="서브넷을 찾을 수 없습니다")
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


def _fetch_topology_sync(conn, project_id: str | None = None) -> dict:
    """동기 방식으로 토폴로지 데이터 수집 (cached_call 내부에서 to_thread로 실행됨).

    project_id 지정 시 해당 프로젝트의 인스턴스·네트워크·라우터만 반환 (user scope).
    None이면 전체 반환 (admin scope).
    """
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

    # user scope: 현재 프로젝트 인스턴스만 표시
    if project_id:
        instance_list = [i for i in instance_list if i.project_id == project_id]
        # 네트워크: 현재 프로젝트 소유 + external + shared 만 유지
        topo.networks = [n for n in topo.networks if n.project_id == project_id or n.is_external or n.is_shared]
        # 라우터: 현재 프로젝트 소유만 유지
        topo.routers = [r for r in topo.routers if getattr(r, "project_id", None) == project_id]

    topo.instances = instance_list
    topo.load_balancers = get_topology_lbs(
        conn,
        project_id=project_id or getattr(conn, "_afterglow_project_id", None),
        instances=[inst.model_dump() for inst in instance_list],
    )
    return topo.model_dump()


@router.get("/topology", response_model=TopologyData)
async def get_topology(
    conn: openstack.connection.Connection = Depends(get_os_conn), cm: CacheMode = Depends(cache_mode)
):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:neutron:{pid}:topology",
            ttl_normal(),
            lambda: _fetch_topology_sync(conn, project_id=pid),
            enabled=cm.enabled,
            refresh=cm.refresh,
        )
    except Exception:
        _logger.exception("토폴로지 조회 실패")
        raise HTTPException(status_code=500, detail="토폴로지 조회 실패")


@router.get("/topology/traffic")
async def get_topology_traffic(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
    all_projects: bool = Query(False, description="admin 전용: 모든 프로젝트 트래픽 조회"),
) -> dict:
    """현재 토폴로지의 모든 리소스 instant 트래픽 (rx/tx bps).

    구조 엔드포인트(/topology)와 분리 — 15s 단주기 폴링 전용.
    `all_projects=true` 는 시스템 admin 만 허용 — admin 토폴로지 페이지용.
    반환: { ts, instances, networks, interfaces, routers, load_balancers, _meta }
    """
    if all_projects:
        if not token_info.get("is_system_admin", False):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
        scope_project_id: str | None = None
        cache_key = "afterglow:neutron:_all:port_mac_map"
    else:
        scope_project_id = token_info.get("project_id", "") or conn._afterglow_project_id
        cache_key = f"afterglow:neutron:{scope_project_id}:port_mac_map"

    # 1) compute 포트맵 — MAC↔port_id↔network_id 매핑 (Redis 캐시, TTL 300s)
    port_map: dict[str, dict] = await cached_call(
        cache_key,
        ttl_static(),
        lambda: neutron.list_project_port_map(conn, scope_project_id),
    )
    # mac_address → {port_id, instance_id, network_id} 역인덱스
    mac_idx: dict[str, dict] = {
        v["mac_address"]: {"port_id": pid, **v} for pid, v in port_map.items() if v.get("mac_address")
    }
    instance_ids = list({v["instance_id"] for v in port_map.values() if v.get("instance_id")})
    # instance → [port_id] 맵 (단일NIC 판별용)
    instance_ports: dict[str, list[str]] = {}
    for pid, v in port_map.items():
        iid = v.get("instance_id")
        if iid:
            instance_ports.setdefault(iid, []).append(pid)

    # 2) PromQL instant queries — 5-fan-out 병렬 실행
    _exclude = r"lo|veth.*|docker.*|cni.*|tap.*|qbr.*"
    interfaces: dict[str, dict] = {}
    instances: dict[str, dict[str, float]] = {}

    if instance_ids:
        # UUID 는 [0-9a-f-] 만 포함 — re.escape 쓰면 \- 로 인해 Prometheus RE2 거부.
        regex = "|".join(instance_ids)
        rx_q = (
            f"sum by (instance_id, device) (rate(node_network_receive_bytes_total"
            f'{{instance_id=~"{regex}",device!~"{_exclude}"}}[2m]))'
        )
        tx_q = rx_q.replace("receive", "transmit")
        # libvirt: NIC 단위 demux. group_left 2단계 중첩으로 mac_address + instance_id 동시 보존.
        lv_rx_q = (
            f"sum by (instance_id, mac_address) ("
            f"(rate(libvirt_domain_interface_stats_receive_bytes_total[2m])"
            f" * on (domain, target_device) group_left(mac_address)"
            f"   libvirt_domain_interface_stats_info)"
            f" * on (domain) group_left(instance_id)"
            f' libvirt_domain_openstack_info{{instance_id=~"{regex}"}})'
        )
        lv_tx_q = lv_rx_q.replace("receive", "transmit")
        try:
            rx_pairs, tx_pairs, lv_rx_pairs, lv_tx_pairs = await asyncio.gather(
                query_instant_multi(rx_q),
                query_instant_multi(tx_q),
                query_instant_multi(lv_rx_q),
                query_instant_multi(lv_tx_q),
            )
        except (PromUnavailable, PromBadQuery) as exc:
            _logger.warning("토폴로지 트래픽 PromQL 실패 — 폴백: %s", exc)
            rx_pairs = tx_pairs = lv_rx_pairs = lv_tx_pairs = []

        # libvirt 결과 → interfaces (NIC demux 주 경로)
        _lv_mac_rx: dict[str, float] = {}
        for labels, val in lv_rx_pairs:
            mac = (labels.get("mac_address") or "").lower()
            iid = labels.get("instance_id")
            info = mac_idx.get(mac)
            if not info or info["instance_id"] != iid:
                continue
            pid = info["port_id"]
            interfaces.setdefault(
                pid,
                {
                    "instance_id": iid,
                    "network_id": info["network_id"],
                    "mac_address": mac,
                    "rx_bps": 0.0,
                    "tx_bps": 0.0,
                },
            )["rx_bps"] = val * 8
            _lv_mac_rx[mac] = val * 8
        for labels, val in lv_tx_pairs:
            mac = (labels.get("mac_address") or "").lower()
            iid = labels.get("instance_id")
            info = mac_idx.get(mac)
            if not info or info["instance_id"] != iid:
                continue
            pid = info["port_id"]
            if pid in interfaces:
                interfaces[pid]["tx_bps"] = val * 8
            else:
                interfaces[pid] = {
                    "instance_id": iid,
                    "network_id": info["network_id"],
                    "mac_address": mac,
                    "rx_bps": 0.0,
                    "tx_bps": val * 8,
                }

        # interfaces → instances / networks 합산
        networks: dict[str, dict[str, float]] = {}
        for ent in interfaces.values():
            iid, nid = ent["instance_id"], ent["network_id"]
            inst = instances.setdefault(iid, {"rx_bps": 0.0, "tx_bps": 0.0})
            inst["rx_bps"] += ent["rx_bps"]
            inst["tx_bps"] += ent["tx_bps"]
            net = networks.setdefault(nid, {"rx_bps": 0.0, "tx_bps": 0.0})
            net["rx_bps"] += ent["rx_bps"]
            net["tx_bps"] += ent["tx_bps"]

        # node_exporter 결과 — libvirt 미관측 인스턴스 보강
        ne_instances: dict[str, dict[str, float]] = {}
        for labels, val in rx_pairs:
            iid = labels.get("instance_id")
            if iid:
                ne_instances.setdefault(iid, {"rx_bps": 0.0, "tx_bps": 0.0})["rx_bps"] = val * 8
        for labels, val in tx_pairs:
            iid = labels.get("instance_id")
            if iid:
                ne_instances.setdefault(iid, {"rx_bps": 0.0, "tx_bps": 0.0})["tx_bps"] = val * 8
        for iid, ne_vals in ne_instances.items():
            if iid in instances:
                continue
            instances[iid] = ne_vals
            # 단일NIC 인스턴스만 networks 합산 (다중NIC는 귀속 네트워크 불명확)
            ports = instance_ports.get(iid, [])
            if len(ports) == 1:
                nid = port_map.get(ports[0], {}).get("network_id", "")
                if nid:
                    net = networks.setdefault(nid, {"rx_bps": 0.0, "tx_bps": 0.0})
                    net["rx_bps"] += ne_vals["rx_bps"]
                    net["tx_bps"] += ne_vals["tx_bps"]
    else:
        networks = {}

    # 3) LB stats — Octavia /stats 차분 (병렬)
    lbs = await asyncio.to_thread(list_load_balancers, conn, scope_project_id)

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
        "interfaces": interfaces,
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
async def get_network(
    network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    try:
        net = await asyncio.to_thread(conn.network.get_network, network_id)
    except Exception:
        raise HTTPException(status_code=404, detail="네트워크를 찾을 수 없습니다")
    # 외부/공유 네트워크는 cross-project 정상 노출이므로 owner check 면제
    if not (getattr(net, "is_router_external", False) or getattr(net, "is_shared", False)):
        assert_resource_owner(net, conn, token_info, not_found_detail="네트워크를 찾을 수 없습니다")
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
        net = await asyncio.to_thread(conn.network.get_network, network_id)
    except Exception:
        raise HTTPException(status_code=404, detail="네트워크를 찾을 수 없습니다")
    assert_resource_owner(net, conn, token_info, not_found_detail="네트워크를 찾을 수 없습니다")
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
