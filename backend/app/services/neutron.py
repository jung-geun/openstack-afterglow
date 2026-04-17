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


def associate_floating_ip(
    conn: openstack.connection.Connection, floating_ip_id: str, instance_id: str
) -> FloatingIpInfo:
    """인스턴스의 첫 번째 포트에 floating IP 연결."""
    ports = list(conn.network.ports(device_id=instance_id))
    if not ports:
        raise RuntimeError("인스턴스에 연결된 포트가 없습니다")
    port_id = ports[0].id
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
    for port in _iter_router_interface_ports(conn):
        rid = port.device_id
        if not rid:
            continue
        if rid not in router_subnets:
            router_subnets[rid] = []
        if rid not in router_subnet_port_count:
            router_subnet_port_count[rid] = {}
        for fip in port.fixed_ips or []:
            sid = fip.get("subnet_id")
            if sid:
                router_subnet_port_count[rid][sid] = router_subnet_port_count[rid].get(sid, 0) + 1
                if sid not in router_subnets[rid]:
                    router_subnets[rid].append(sid)

    # 4. 전체 라우터
    topo_routers = []
    for r in conn.network.routers():
        ext_net_id = None
        if r.external_gateway_info:
            ext_net_id = r.external_gateway_info.get("network_id")
        dvr_sids = [sid for sid, cnt in router_subnet_port_count.get(r.id, {}).items() if cnt > 1]
        topo_routers.append(
            TopologyRouter(
                id=r.id,
                name=r.name or "",
                status=r.status or "",
                external_gateway_network_id=ext_net_id,
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


def update_port_security_groups(
    conn: openstack.connection.Connection, port_id: str, security_group_ids: list[str]
) -> dict:
    port = conn.network.update_port(port_id, security_groups=security_group_ids)
    return {
        "id": port.id,
        "security_group_ids": port.security_group_ids or [],
    }


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
