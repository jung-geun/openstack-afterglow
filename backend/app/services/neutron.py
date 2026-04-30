from __future__ import annotations

import logging as _logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from app.models.storage import (
    FloatingIpInfo,
    NetworkDetail,
    NetworkInfo,
    RouterDetail,
    RouterInfo,
    RouterInterface,
    SubnetDetail,
    TopologyData,
    TopologyNetwork,
    TopologyRouter,
)

_ROUTER_IFACE_OWNERS = [
    "network:router_interface",
    "network:router_interface_distributed",
    "network:ha_router_replicated_interface",
]


def _iter_router_interface_ports(conn, **kwargs):
    """DVR/HA를 포함한 모든 라우터 인터페이스 포트를 순회."""
    for owner in _ROUTER_IFACE_OWNERS:
        yield from conn.network.ports(device_owner=owner, **kwargs)


def list_networks(conn: openstack.connection.Connection, project_id: str | None = None) -> list[NetworkInfo]:
    result = []
    for n in conn.network.networks():
        if project_id and not (
            bool(n.is_router_external) or bool(n.is_shared) or getattr(n, "project_id", None) == project_id
        ):
            continue
        result.append(_net_to_info(n))
    return result


def get_network(conn: openstack.connection.Connection, network_id: str) -> NetworkInfo:
    n = conn.network.get_network(network_id)
    return _net_to_info(n)


def get_network_detail(conn: openstack.connection.Connection, network_id: str) -> NetworkDetail:
    n = conn.network.get_network(network_id)

    subnet_details = []
    for subnet_id in n.subnet_ids or []:
        try:
            s = conn.network.get_subnet(subnet_id)
            subnet_details.append(
                SubnetDetail(
                    id=s.id,
                    name=s.name or "",
                    cidr=s.cidr or "",
                    gateway_ip=s.gateway_ip,
                    dhcp_enabled=bool(s.is_dhcp_enabled),
                )
            )
        except Exception:
            continue

    # 이 네트워크에 연결된 라우터 찾기 (router_interface 포트 기준)
    router_map: dict[str, RouterInfo] = {}
    try:
        ports = list(_iter_router_interface_ports(conn, network_id=network_id))
        for port in ports:
            router_id = port.device_id
            if not router_id:
                continue
            if router_id not in router_map:
                try:
                    r = conn.network.get_router(router_id)
                    ext_net_id = None
                    if r.external_gateway_info:
                        ext_net_id = r.external_gateway_info.get("network_id")
                    router_map[router_id] = RouterInfo(
                        id=r.id,
                        name=r.name or "",
                        external_gateway_network_id=ext_net_id,
                        connected_subnet_ids=[],
                    )
                except Exception:
                    continue
            # 포트의 fixed_ips에서 서브넷 ID 추출
            for fixed_ip in port.fixed_ips or []:
                sid = fixed_ip.get("subnet_id")
                if sid and sid not in router_map[router_id].connected_subnet_ids:
                    router_map[router_id].connected_subnet_ids.append(sid)
    except Exception:
        pass

    return NetworkDetail(
        id=n.id,
        name=n.name or "",
        status=n.status,
        subnets=list(n.subnet_ids or []),
        is_external=bool(n.is_router_external),
        is_shared=bool(n.is_shared),
        subnet_details=subnet_details,
        routers=list(router_map.values()),
    )


def create_network(conn: openstack.connection.Connection, name: str) -> NetworkInfo:
    n = conn.network.create_network(name=name)
    return _net_to_info(n)


def delete_network(conn: openstack.connection.Connection, network_id: str) -> None:
    conn.network.delete_network(network_id, ignore_missing=True)


def create_subnet(
    conn: openstack.connection.Connection,
    network_id: str,
    name: str,
    cidr: str,
    gateway_ip: str | None = None,
    enable_dhcp: bool = True,
) -> SubnetDetail:
    kwargs = {
        "network_id": network_id,
        "name": name,
        "cidr": cidr,
        "ip_version": 4,
        "is_dhcp_enabled": enable_dhcp,
    }
    if gateway_ip:
        kwargs["gateway_ip"] = gateway_ip
    s = conn.network.create_subnet(**kwargs)
    return SubnetDetail(
        id=s.id,
        name=s.name or "",
        cidr=s.cidr or "",
        gateway_ip=s.gateway_ip,
        dhcp_enabled=bool(s.is_dhcp_enabled),
    )


def delete_subnet(conn: openstack.connection.Connection, subnet_id: str) -> None:
    conn.network.delete_subnet(subnet_id, ignore_missing=True)


def update_subnet(
    conn: openstack.connection.Connection,
    subnet_id: str,
    name: str | None = None,
    gateway_ip: str | None = None,
    enable_dhcp: bool | None = None,
) -> SubnetDetail:
    kwargs: dict = {}
    if name is not None:
        kwargs["name"] = name
    if gateway_ip is not None:
        kwargs["gateway_ip"] = gateway_ip
    if enable_dhcp is not None:
        kwargs["is_dhcp_enabled"] = enable_dhcp
    s = conn.network.update_subnet(subnet_id, **kwargs)
    return SubnetDetail(
        id=s.id,
        name=s.name or "",
        cidr=s.cidr or "",
        gateway_ip=s.gateway_ip,
        dhcp_enabled=bool(s.is_dhcp_enabled),
    )


def delete_port(conn: openstack.connection.Connection, port_id: str) -> None:
    conn.network.delete_port(port_id, ignore_missing=True)


def cleanup_instance_fips(conn: openstack.connection.Connection, instance_id: str) -> None:
    """인스턴스 포트에 연결된 Floating IP만 해제하고 삭제한다.

    Neutron /v2.0/floatingips 는 device_id 필터를 지원하지 않으므로
    포트 기반으로 대상 FIP를 식별한다 (Nova가 인스턴스 포트에 device_id를 세팅).
    """
    log = _logging.getLogger(__name__)
    try:
        ports = list(conn.network.ports(device_id=instance_id))
    except Exception:
        log.warning("cleanup_instance_fips: 포트 조회 실패 (instance=%s)", instance_id, exc_info=True)
        return
    port_ids = {p.id for p in ports}
    if not port_ids:
        return
    try:
        fips = [f for f in conn.network.ips() if f.port_id in port_ids]
    except Exception:
        log.warning("cleanup_instance_fips: FIP 조회 실패 (instance=%s)", instance_id, exc_info=True)
        return
    for fip in fips:
        try:
            conn.network.update_ip(fip.id, port_id=None)
            conn.network.delete_ip(fip.id, ignore_missing=True)
        except Exception:
            log.warning("cleanup_instance_fips: FIP %s 정리 실패", fip.id, exc_info=True)


# ---------------------------------------------------------------------------
# Floating IP
# ---------------------------------------------------------------------------


def get_network_quota(conn: openstack.connection.Connection, project_id: str) -> dict:
    """프로젝트의 Neutron 할당량 (limit + in_use) 조회."""

    def _q(q, key):
        if isinstance(q, dict):
            return q.get(key, {"limit": -1, "in_use": 0})
        v = getattr(q, key, None)
        if isinstance(v, dict):
            return {"limit": v.get("limit", -1), "in_use": v.get("used", v.get("in_use", 0))}
        return {"limit": int(v) if v is not None else -1, "in_use": 0}

    try:
        # details=True는 used 필드를 포함한 상세 할당량 반환
        quota = conn.network.get_quota(project_id, details=True)
        quota_dict = quota.to_dict() if hasattr(quota, "to_dict") else {}
        keys = ["floatingip", "security_group", "security_group_rule", "network", "port", "router", "subnet"]
        result = {k: _q(quota_dict, k) for k in keys}
        # Fallback: quota details가 in_use=0으로 반환할 때 실제 리소스 카운트
        if result["floatingip"]["in_use"] == 0:
            try:
                result["floatingip"]["in_use"] = sum(1 for _ in conn.network.ips(project_id=project_id))
            except Exception:
                pass
        if result["port"]["in_use"] == 0:
            try:
                result["port"]["in_use"] = sum(1 for _ in conn.network.ports(project_id=project_id))
            except Exception:
                pass
        return result
    except Exception:
        import logging as _logging

        _logging.getLogger(__name__).warning("Neutron quota details 조회 실패 — fallback", exc_info=True)
        try:
            # fallback: details 없이 limit만 조회
            quota = conn.network.get_quota(project_id)
            quota_dict = quota.to_dict() if hasattr(quota, "to_dict") else {}
            keys = ["floatingip", "security_group", "security_group_rule", "network", "port", "router", "subnet"]
            result = {}
            for k in keys:
                val = quota_dict.get(k, -1)
                result[k] = {"limit": int(val) if val is not None else -1, "in_use": 0}
            return result
        except Exception:
            return {
                k: {"limit": -1, "in_use": 0}
                for k in ["floatingip", "security_group", "security_group_rule", "network", "port", "router", "subnet"]
            }


def list_floating_ips(conn: openstack.connection.Connection, project_id: str | None = None) -> list[FloatingIpInfo]:
    kwargs: dict = {}
    if project_id:
        kwargs["project_id"] = project_id
    return [_fip_to_info(f) for f in conn.network.ips(**kwargs)]


def create_floating_ip(conn: openstack.connection.Connection, floating_network_id: str) -> FloatingIpInfo:
    fip = conn.network.create_ip(floating_network_id=floating_network_id)
    return _fip_to_info(fip)


def find_external_network_for_subnets(
    conn: openstack.connection.Connection,
    subnet_ids: set[str],
) -> str | None:
    """주어진 서브넷에 라우터 인터페이스로 연결된 외부 게이트웨이 네트워크 ID를 반환.

    - 라우터의 external_gateway_info.network_id를 사용해 reachable한 외부망을 결정.
    - 매칭 라우터가 없거나 라우터에 외부 게이트웨이가 설정되지 않았으면 None.
    """
    if not subnet_ids:
        return None
    candidate_router_ids: set[str] = set()
    for iface_port in _iter_router_interface_ports(conn):
        iface_subnet_ids = {fi.get("subnet_id") for fi in (iface_port.fixed_ips or [])}
        if iface_subnet_ids & subnet_ids and iface_port.device_id:
            candidate_router_ids.add(iface_port.device_id)
    if not candidate_router_ids:
        return None
    for router in conn.network.routers():
        if router.id in candidate_router_ids and router.external_gateway_info:
            ext_net_id = router.external_gateway_info.get("network_id")
            if ext_net_id:
                return ext_net_id
    return None


def associate_floating_ip(
    conn: openstack.connection.Connection,
    floating_ip_id: str,
    instance_id: str,
    port_id: str | None = None,
) -> FloatingIpInfo:
    """인스턴스 포트에 floating IP 연결. port_id 미지정 시 FIP 미점유 첫 포트를 선택한다."""
    if not port_id:
        ports = list(conn.network.ports(device_id=instance_id))
        if not ports:
            raise RuntimeError("인스턴스에 연결된 포트가 없습니다")
        used_port_ids = {f.port_id for f in conn.network.ips() if f.port_id}
        available = [p for p in ports if p.id not in used_port_ids]
        if not available:
            raise RuntimeError("모든 인터페이스에 이미 Floating IP가 할당되어 있습니다")
        port_id = available[0].id
    fip = conn.network.update_ip(floating_ip_id, port_id=port_id)
    return _fip_to_info(fip)


def disassociate_floating_ip(conn: openstack.connection.Connection, floating_ip_id: str) -> FloatingIpInfo:
    fip = conn.network.update_ip(floating_ip_id, port_id=None)
    return _fip_to_info(fip)


def delete_floating_ip(conn: openstack.connection.Connection, floating_ip_id: str) -> None:
    conn.network.delete_ip(floating_ip_id, ignore_missing=True)


def get_topology(conn: openstack.connection.Connection) -> TopologyData:
    """배치 조회로 전체 토폴로지 데이터를 수집. OpenStack API 5회 호출."""
    # 1. 전체 네트워크
    all_networks = list(conn.network.networks())

    # 2. 전체 서브넷 → 맵 구축
    subnet_map: dict[str, SubnetDetail] = {}  # subnet_id → SubnetDetail
    subnet_network_map: dict[str, str] = {}  # subnet_id → network_id
    for s in conn.network.subnets():
        subnet_map[s.id] = SubnetDetail(
            id=s.id,
            name=s.name or "",
            cidr=s.cidr or "",
            gateway_ip=s.gateway_ip,
            dhcp_enabled=bool(s.is_dhcp_enabled),
        )
        subnet_network_map[s.id] = s.network_id

    # 3. 라우터 인터페이스 포트 → router_id→[subnet_ids] 맵 (DVR/HA 포함)
    router_subnets: dict[str, list[str]] = {}
    router_subnet_port_count: dict[str, dict[str, int]] = {}  # rid → {sid → port 수}
    router_interface_ips: dict[str, list[dict]] = {}  # rid → [{ip_address, subnet_id}]
    for port in _iter_router_interface_ports(conn):
        rid = port.device_id
        if not rid:
            continue
        if rid not in router_subnets:
            router_subnets[rid] = []
        if rid not in router_subnet_port_count:
            router_subnet_port_count[rid] = {}
        if rid not in router_interface_ips:
            router_interface_ips[rid] = []
        for fip in port.fixed_ips or []:
            sid = fip.get("subnet_id")
            ip_addr = fip.get("ip_address")
            if sid:
                router_subnet_port_count[rid][sid] = router_subnet_port_count[rid].get(sid, 0) + 1
                if sid not in router_subnets[rid]:
                    router_subnets[rid].append(sid)
            # 중복 IP 제거 (DVR replicated 포트는 같은 IP 여러 번 나올 수 있음)
            if (
                ip_addr
                and sid
                and not any(e["ip_address"] == ip_addr and e["subnet_id"] == sid for e in router_interface_ips[rid])
            ):
                router_interface_ips[rid].append({"ip_address": ip_addr, "subnet_id": sid})

    # 4. 전체 라우터
    topo_routers = []
    for r in conn.network.routers():
        ext_net_id = None
        ext_gw_ips: list[str] = []
        if r.external_gateway_info:
            ext_net_id = r.external_gateway_info.get("network_id")
            for efip in r.external_gateway_info.get("external_fixed_ips", []):
                ip = efip.get("ip_address")
                if ip:
                    ext_gw_ips.append(ip)
        dvr_sids = [sid for sid, cnt in router_subnet_port_count.get(r.id, {}).items() if cnt > 1]
        topo_routers.append(
            TopologyRouter(
                id=r.id,
                name=r.name or "",
                status=r.status or "",
                external_gateway_network_id=ext_net_id,
                external_gateway_ips=ext_gw_ips,
                interface_ips=router_interface_ips.get(r.id, []),
                is_distributed=bool(getattr(r, "is_distributed", False)),
                is_ha=bool(getattr(r, "is_ha", False)),
                connected_subnet_ids=router_subnets.get(r.id, []),
                dvr_subnet_ids=dvr_sids,
                project_id=getattr(r, "project_id", None),
            )
        )

    # 5. 네트워크별 서브넷 grouping
    network_subnets: dict[str, list[SubnetDetail]] = {}
    for subnet_id, net_id in subnet_network_map.items():
        if net_id not in network_subnets:
            network_subnets[net_id] = []
        if subnet_id in subnet_map:
            network_subnets[net_id].append(subnet_map[subnet_id])

    topo_networks = [
        TopologyNetwork(
            id=n.id,
            name=n.name or "",
            status=n.status or "",
            is_external=bool(n.is_router_external),
            is_shared=bool(n.is_shared),
            project_id=getattr(n, "project_id", None),
            subnet_details=network_subnets.get(n.id, []),
        )
        for n in all_networks
    ]

    return TopologyData(
        networks=topo_networks,
        routers=topo_routers,
        instances=[],  # API 핸들러에서 nova 데이터 주입
        floating_ips=list_floating_ips(conn),
    )


# ---------------------------------------------------------------------------
# 라우터 CRUD
# ---------------------------------------------------------------------------


def list_routers(conn: openstack.connection.Connection, project_id: str | None = None) -> list[RouterInfo]:
    kwargs: dict = {}
    if project_id:
        kwargs["project_id"] = project_id
    result = []
    for r in conn.network.routers(**kwargs):
        ext_net_id = None
        if r.external_gateway_info:
            ext_net_id = r.external_gateway_info.get("network_id")
        # connected subnets via router_interface ports
        subnet_ids: list[str] = []
        try:
            for port in _iter_router_interface_ports(conn, device_id=r.id):
                for fip in port.fixed_ips or []:
                    sid = fip.get("subnet_id")
                    if sid and sid not in subnet_ids:
                        subnet_ids.append(sid)
        except Exception:
            pass
        result.append(
            RouterInfo(
                id=r.id,
                name=r.name or "",
                status=r.status or "",
                project_id=getattr(r, "project_id", None),
                external_gateway_network_id=ext_net_id,
                connected_subnet_ids=subnet_ids,
            )
        )
    return result


def get_router_detail(conn: openstack.connection.Connection, router_id: str) -> RouterDetail:
    r = conn.network.get_router(router_id)
    ext_net_id = None
    ext_net_name = None
    if r.external_gateway_info:
        ext_net_id = r.external_gateway_info.get("network_id")
        if ext_net_id:
            try:
                ext_net = conn.network.get_network(ext_net_id)
                ext_net_name = ext_net.name or ext_net_id
            except Exception:
                pass

    interfaces: list[RouterInterface] = []
    for port in _iter_router_interface_ports(conn, device_id=r.id):
        for fip in port.fixed_ips or []:
            sid = fip.get("subnet_id", "")
            ip = fip.get("ip_address", "")
            subnet_name = ""
            net_id = port.network_id or ""
            try:
                s = conn.network.get_subnet(sid)
                subnet_name = s.name or sid
            except Exception:
                pass
            interfaces.append(
                RouterInterface(
                    id=port.id,
                    subnet_id=sid,
                    subnet_name=subnet_name,
                    network_id=net_id,
                    ip_address=ip,
                )
            )

    return RouterDetail(
        id=r.id,
        name=r.name or "",
        status=r.status or "",
        project_id=getattr(r, "project_id", None),
        external_gateway_network_id=ext_net_id,
        external_gateway_network_name=ext_net_name,
        interfaces=interfaces,
    )


def create_router(
    conn: openstack.connection.Connection, name: str, external_network_id: str | None = None
) -> RouterInfo:
    kwargs: dict = {"name": name}
    if external_network_id:
        kwargs["external_gateway_info"] = {"network_id": external_network_id}
    r = conn.network.create_router(**kwargs)
    ext_net_id = None
    if r.external_gateway_info:
        ext_net_id = r.external_gateway_info.get("network_id")
    return RouterInfo(
        id=r.id,
        name=r.name or "",
        status=r.status or "",
        project_id=getattr(r, "project_id", None),
        external_gateway_network_id=ext_net_id,
    )


def delete_router(conn: openstack.connection.Connection, router_id: str) -> None:
    conn.network.delete_router(router_id, ignore_missing=True)


def add_router_interface(conn: openstack.connection.Connection, router_id: str, subnet_id: str) -> dict:
    result = conn.network.add_interface_to_router(router_id, subnet_id=subnet_id)
    return {"subnet_id": result.get("subnet_id", subnet_id), "port_id": result.get("port_id", "")}


def remove_router_interface(conn: openstack.connection.Connection, router_id: str, subnet_id: str) -> None:
    conn.network.remove_interface_from_router(router_id, subnet_id=subnet_id)


def set_router_gateway(conn: openstack.connection.Connection, router_id: str, external_network_id: str) -> None:
    conn.network.update_router(router_id, external_gateway_info={"network_id": external_network_id})


def remove_router_gateway(conn: openstack.connection.Connection, router_id: str) -> None:
    conn.network.update_router(router_id, external_gateway_info=None)


def list_instance_ports(conn: openstack.connection.Connection, instance_id: str) -> list[dict]:
    """인스턴스에 연결된 포트 목록 반환."""
    ports = list(conn.network.ports(device_id=instance_id))
    return [
        {
            "id": p.id,
            "network_id": p.network_id,
            "mac_address": p.mac_address,
            "fixed_ips": p.fixed_ips or [],
            "security_group_ids": p.security_group_ids or [],
            "status": p.status,
        }
        for p in ports
    ]


def _sg_to_dict(sg) -> dict:
    return {
        "id": sg.id,
        "name": sg.name,
        "description": sg.description,
        "rules": [
            {
                "id": r["id"],
                "direction": r["direction"],
                "protocol": r.get("protocol"),
                "port_range_min": r.get("port_range_min"),
                "port_range_max": r.get("port_range_max"),
                "remote_ip_prefix": r.get("remote_ip_prefix"),
                "ethertype": r.get("ethertype"),
            }
            for r in (sg.security_group_rules or [])
        ],
    }


def list_security_groups(conn: openstack.connection.Connection, project_id: str | None = None) -> list[dict]:
    kwargs: dict = {}
    if project_id:
        kwargs["project_id"] = project_id
    return [_sg_to_dict(sg) for sg in conn.network.security_groups(**kwargs)]


def create_security_group(conn: openstack.connection.Connection, name: str, description: str = "") -> dict:
    sg = conn.network.create_security_group(name=name, description=description)
    return _sg_to_dict(sg)


def delete_security_group(conn: openstack.connection.Connection, sg_id: str) -> None:
    conn.network.delete_security_group(sg_id, ignore_missing=True)


def create_security_group_rule(
    conn: openstack.connection.Connection,
    sg_id: str,
    direction: str,
    protocol: str | None = None,
    port_range_min: int | None = None,
    port_range_max: int | None = None,
    remote_ip_prefix: str | None = None,
    ethertype: str = "IPv4",
    remote_group_id: str | None = None,
) -> dict:
    kwargs: dict = {
        "security_group_id": sg_id,
        "direction": direction,
        "ether_type": ethertype,
    }
    if protocol:
        kwargs["protocol"] = protocol
    if port_range_min is not None:
        kwargs["port_range_min"] = port_range_min
    if port_range_max is not None:
        kwargs["port_range_max"] = port_range_max
    if remote_ip_prefix:
        kwargs["remote_ip_prefix"] = remote_ip_prefix
    if remote_group_id:
        kwargs["remote_group_id"] = remote_group_id
    rule = conn.network.create_security_group_rule(**kwargs)
    return {
        "id": rule.id,
        "direction": rule.direction,
        "protocol": rule.protocol,
        "port_range_min": rule.port_range_min,
        "port_range_max": rule.port_range_max,
        "remote_ip_prefix": rule.remote_ip_prefix,
        "ethertype": rule.ether_type,
    }


def delete_security_group_rule(conn: openstack.connection.Connection, rule_id: str) -> None:
    conn.network.delete_security_group_rule(rule_id, ignore_missing=True)


_UNION_EGRESS_RULES: list[dict] = [
    {"protocol": "tcp", "port_range_min": 2049, "port_range_max": 2049},  # NFS
    {"protocol": "udp", "port_range_min": 2049, "port_range_max": 2049},  # NFS UDP
    {"protocol": "tcp", "port_range_min": 6789, "port_range_max": 6789},  # CephFS mon v1
    {"protocol": "tcp", "port_range_min": 3300, "port_range_max": 3300},  # Ceph msgr v2
    {"protocol": "tcp", "port_range_min": 80, "port_range_max": 80},  # envmgr-init HTTP
    {"protocol": "tcp", "port_range_min": 443, "port_range_max": 443},  # envmgr-init HTTPS
]


def ensure_union_egress_sg(
    conn: openstack.connection.Connection, project_id: str, sg_name: str = "union-egress-default"
) -> str:
    """Union VM용 egress SG를 idempotent하게 확보하고 SG 이름을 반환한다.

    SG가 없으면 생성 후 NFS/CephFS/HTTP(S) egress rule을 추가한다.
    이미 있으면 누락된 rule만 보충한다.
    """
    sgs = list_security_groups(conn, project_id=project_id)
    existing = next((sg for sg in sgs if sg["name"] == sg_name), None)

    if existing is None:
        sg = create_security_group(conn, sg_name, "Union VM egress — NFS/CephFS/HTTP(S)")
        sg_id = sg["id"]
        existing_rules: list[dict] = []
    else:
        sg_id = existing["id"]
        existing_rules = existing.get("rules", [])

    # (protocol, min, max)로 기존 egress rule 목록 색인
    existing_keys = {
        (r.get("protocol"), r.get("port_range_min"), r.get("port_range_max"))
        for r in existing_rules
        if r.get("direction") == "egress"
    }

    for rule in _UNION_EGRESS_RULES:
        key = (rule["protocol"], rule["port_range_min"], rule["port_range_max"])
        if key not in existing_keys:
            create_security_group_rule(
                conn,
                sg_id,
                direction="egress",
                protocol=rule["protocol"],
                port_range_min=rule["port_range_min"],
                port_range_max=rule["port_range_max"],
                remote_ip_prefix="0.0.0.0/0",
            )

    return sg_name


_MONITORING_INGRESS_RULES: list[dict] = [
    {"protocol": "tcp", "port_range_min": 9100, "port_range_max": 9100},  # node_exporter
    {"protocol": "tcp", "port_range_min": 9400, "port_range_max": 9400},  # dcgm_exporter (GPU)
]


def ensure_monitoring_ingress_sg(
    conn: openstack.connection.Connection,
    project_id: str,
    sg_name: str = "monitoring",
    scrape_cidr: str = "",
) -> str:
    """Prometheus scrape용 ingress SG를 idempotent하게 확보하고 SG 이름을 반환한다.

    scrape_cidr이 비어있으면 ValueError를 발생시킨다(환경별 명시 주입 필수).
    SG가 없으면 생성 후 node_exporter/dcgm_exporter ingress rule을 추가한다.
    이미 있으면 누락된 rule만 보충한다.
    """
    if not scrape_cidr:
        raise ValueError("monitoring_scrape_cidr must be set — env 주입 필수")

    sgs = list_security_groups(conn, project_id=project_id)
    existing = next((sg for sg in sgs if sg["name"] == sg_name), None)

    if existing is None:
        sg = create_security_group(conn, sg_name, "Prometheus scrape — node_exporter/dcgm_exporter ingress")
        sg_id = sg["id"]
        existing_rules: list[dict] = []
    else:
        sg_id = existing["id"]
        existing_rules = existing.get("rules", [])

    existing_keys = {
        (r.get("protocol"), r.get("port_range_min"), r.get("port_range_max"), r.get("remote_ip_prefix"))
        for r in existing_rules
        if r.get("direction") == "ingress"
    }

    for rule in _MONITORING_INGRESS_RULES:
        key = (rule["protocol"], rule["port_range_min"], rule["port_range_max"], scrape_cidr)
        if key not in existing_keys:
            create_security_group_rule(
                conn,
                sg_id,
                direction="ingress",
                protocol=rule["protocol"],
                port_range_min=rule["port_range_min"],
                port_range_max=rule["port_range_max"],
                remote_ip_prefix=scrape_cidr,
            )

    return sg_name


def update_port_security_groups(
    conn: openstack.connection.Connection, port_id: str, security_group_ids: list[str]
) -> dict:
    port = conn.network.update_port(port_id, security_groups=security_group_ids)
    return {
        "id": port.id,
        "security_group_ids": port.security_group_ids or [],
    }


# ---------------------------------------------------------------------------
# 프로젝트 기본 네트워크 (Default Network) — 동기 Neutron 연산
# ---------------------------------------------------------------------------

_default_net_logger = _logging.getLogger(__name__)


def _find_external_network(conn: openstack.connection.Connection) -> str | None:
    """첫 번째 외부(provider) 네트워크 ID를 반환. 없으면 None."""
    try:
        for n in conn.network.networks():
            if n.is_router_external:
                return n.id
    except Exception:
        pass
    return None


def _find_existing_router_for_subnet(
    conn: openstack.connection.Connection,
    subnet_id: str,
) -> str | None:
    """서브넷에 이미 연결된 라우터가 있으면 그 ID를 반환."""
    try:
        for port in _iter_router_interface_ports(conn, network_id=None):
            for fip in port.fixed_ips or []:
                if fip.get("subnet_id") == subnet_id:
                    return port.device_id
    except Exception:
        pass
    return None


def provision_default_network(
    conn: openstack.connection.Connection,
    project_id: str,
    external_network_id: str | None = None,
    cidr: str = "192.168.0.0/24",
) -> tuple[str, str | None, str | None, bool]:
    """Neutron에서 "Default" 네트워크를 찾거나 새로 생성한다 (동기).

    - 외부 네트워크 미지정 시 자동 감지
    - 기존 네트워크에 라우터가 없으면 자동 생성하여 연결

    Returns:
        (network_id, subnet_id, router_id, newly_created)
    """
    # 외부 네트워크 자동 감지 (미설정 시)
    if not external_network_id:
        external_network_id = _find_external_network(conn)

    # ── Neutron 검색 ─────────────────────────────────────────────────────────
    try:
        existing = [
            n for n in conn.network.networks(project_id=project_id) if n.name == "Default" and not n.is_router_external
        ]
        if existing:
            net = existing[0]
            subnet_id = net.subnet_ids[0] if net.subnet_ids else None
            router_id: str | None = None

            # 기존 네트워크에 라우터가 연결되어 있는지 확인 → 없으면 자동 생성
            if subnet_id and external_network_id:
                router_id = _find_existing_router_for_subnet(conn, subnet_id)
                if not router_id:
                    try:
                        router = conn.network.create_router(
                            name="Default",
                            external_gateway_info={"network_id": external_network_id},
                        )
                        conn.network.add_interface_to_router(router.id, subnet_id=subnet_id)
                        router_id = router.id
                        _default_net_logger.info("기존 Default 네트워크(%s)에 라우터(%s) 자동 연결", net.id, router_id)
                    except Exception:
                        _default_net_logger.warning("기존 네트워크에 라우터 자동 연결 실패", exc_info=True)

            return net.id, subnet_id, router_id, False
    except Exception:
        _default_net_logger.warning("Neutron 네트워크 검색 실패", exc_info=True)

    # ── 새로 생성 ────────────────────────────────────────────────────────────
    net = None
    subnet = None
    router = None
    subnet_id = None
    router_id = None
    try:
        net = conn.network.create_network(name="Default")
        # CIDR의 첫 번째 호스트를 게이트웨이로 사용 (예: 192.168.0.0/24 → 192.168.0.1)
        try:
            import ipaddress

            network_addr = ipaddress.IPv4Network(cidr, strict=False)
            gateway: str | None = str(list(network_addr.hosts())[0])
        except Exception:
            gateway = None
        subnet = conn.network.create_subnet(
            network_id=net.id,
            name="Default",
            cidr=cidr,
            ip_version=4,
            is_dhcp_enabled=True,
            **({} if gateway is None else {"gateway_ip": gateway}),
        )
        subnet_id = subnet.id

        # 라우터 생성 및 외부 네트워크 게이트웨이 연결
        if external_network_id:
            router = conn.network.create_router(
                name="Default",
                external_gateway_info={"network_id": external_network_id},
            )
            conn.network.add_interface_to_router(router.id, subnet_id=subnet.id)
            router_id = router.id
        else:
            _default_net_logger.warning("외부 네트워크를 찾을 수 없어 라우터 생성을 건너뜁니다")
    except Exception as exc:
        _default_net_logger.error("Default 네트워크 생성 실패, 롤백", exc_info=True)
        # 생성된 리소스 정리
        if router:
            try:
                if subnet:
                    conn.network.remove_interface_from_router(router.id, subnet_id=subnet.id)
                conn.network.delete_router(router.id, ignore_missing=True)
            except Exception:
                pass
        if subnet:
            try:
                conn.network.delete_subnet(subnet.id, ignore_missing=True)
            except Exception:
                pass
        if net:
            try:
                conn.network.delete_network(net.id, ignore_missing=True)
            except Exception:
                pass
        raise RuntimeError("Default 네트워크 생성 실패") from exc

    return net.id, subnet_id, router_id, True


def _fip_to_info(f) -> FloatingIpInfo:
    return FloatingIpInfo(
        id=f.id,
        floating_ip_address=f.floating_ip_address,
        fixed_ip_address=f.fixed_ip_address,
        status=f.status or "",
        port_id=f.port_id,
        floating_network_id=f.floating_network_id,
        project_id=getattr(f, "project_id", None),
    )


def _net_to_info(n) -> NetworkInfo:
    return NetworkInfo(
        id=n.id,
        name=n.name or "",
        status=n.status,
        subnets=list(n.subnet_ids or []),
        is_external=bool(n.is_router_external),
        is_shared=bool(n.is_shared),
    )
