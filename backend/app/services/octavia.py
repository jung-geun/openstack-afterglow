"""Octavia (OpenStack Load Balancer) 서비스 래퍼."""

import openstack
from typing import Optional


def _lb_to_dict(lb) -> dict:
    return {
        "id": lb.id,
        "name": lb.name or "",
        "description": getattr(lb, 'description', "") or "",
        "status": getattr(lb, 'provisioning_status', "") or "",
        "operating_status": getattr(lb, 'operating_status', "") or "",
        "vip_address": getattr(lb, 'vip_address', None),
        "vip_subnet_id": getattr(lb, 'vip_subnet_id', None),
        "vip_network_id": getattr(lb, 'vip_network_id', None),
        "project_id": getattr(lb, 'project_id', None),
    }


def _listener_to_dict(l) -> dict:
    return {
        "id": l.id,
        "name": l.name or "",
        "protocol": getattr(l, 'protocol', "") or "",
        "protocol_port": getattr(l, 'protocol_port', 0),
        "status": getattr(l, 'provisioning_status', "") or "",
        "default_pool_id": getattr(l, 'default_pool_id', None),
        "load_balancer_id": getattr(l, 'load_balancer_id', None),
    }


def _pool_to_dict(p) -> dict:
    return {
        "id": p.id,
        "name": p.name or "",
        "protocol": getattr(p, 'protocol', "") or "",
        "lb_algorithm": getattr(p, 'lb_algorithm', "") or "",
        "status": getattr(p, 'provisioning_status', "") or "",
        "health_monitor_id": getattr(p, 'health_monitor_id', None),
        "load_balancer_id": (getattr(p, 'load_balancers', None) or [{}])[0].get("id") if getattr(p, 'load_balancers', None) else None,
    }


def _member_to_dict(m) -> dict:
    return {
        "id": m.id,
        "name": m.name or "",
        "address": getattr(m, 'address', "") or "",
        "protocol_port": getattr(m, 'protocol_port', 0),
        "weight": getattr(m, 'weight', 1),
        "status": getattr(m, 'provisioning_status', "") or "",
        "subnet_id": getattr(m, 'subnet_id', None),
    }


def _hm_to_dict(hm) -> dict:
    return {
        "id": hm.id,
        "name": hm.name or "",
        "type": getattr(hm, 'type', "") or "",
        "delay": getattr(hm, 'delay', 5),
        "timeout": getattr(hm, 'timeout', 5),
        "max_retries": getattr(hm, 'max_retries', 3),
        "status": getattr(hm, 'provisioning_status', "") or "",
    }


# ---------------------------------------------------------------------------
# Load Balancers
# ---------------------------------------------------------------------------

def list_load_balancers(conn: openstack.connection.Connection, project_id: Optional[str] = None) -> list[dict]:
    kwargs = {}
    if project_id:
        kwargs["project_id"] = project_id
    return [_lb_to_dict(lb) for lb in conn.load_balancer.load_balancers(**kwargs)]


def get_load_balancer(conn: openstack.connection.Connection, lb_id: str) -> dict:
    return _lb_to_dict(conn.load_balancer.get_load_balancer(lb_id))


def create_load_balancer(
    conn: openstack.connection.Connection,
    name: str,
    vip_subnet_id: str,
    description: str = "",
) -> dict:
    lb = conn.load_balancer.create_load_balancer(
        name=name,
        vip_subnet_id=vip_subnet_id,
        description=description,
    )
    return _lb_to_dict(lb)


def delete_load_balancer(conn: openstack.connection.Connection, lb_id: str, cascade: bool = True) -> None:
    conn.load_balancer.delete_load_balancer(lb_id, cascade=cascade, ignore_missing=True)


def get_lb_status_tree(conn: openstack.connection.Connection, lb_id: str) -> dict:
    """로드밸런서 상태 트리 조회 (Octavia status tree API).
    오류 발생 위치를 계층적으로 확인하는 데 사용.
    """
    try:
        # openstacksdk가 status tree를 직접 지원하지 않으므로 raw session 사용
        lb = conn.load_balancer.get_load_balancer(lb_id)
        endpoint = conn.load_balancer.get_endpoint()
        resp = conn.load_balancer._session.get(
            f"{endpoint.rstrip('/')}/lbaas/loadbalancers/{lb_id}/status"
        )
        data = resp.json() if hasattr(resp, 'json') else {}
        return data.get("statuses", {}).get("loadbalancer", {})
    except Exception:
        pass
    # fallback: 기본 LB 정보만 반환
    try:
        lb = conn.load_balancer.get_load_balancer(lb_id)
        return {
            "id": lb.id,
            "name": lb.name,
            "provisioning_status": getattr(lb, 'provisioning_status', ''),
            "operating_status": getattr(lb, 'operating_status', ''),
            "listeners": [],
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------

def list_listeners(conn: openstack.connection.Connection, lb_id: Optional[str] = None) -> list[dict]:
    kwargs = {}
    if lb_id:
        kwargs["load_balancer_id"] = lb_id
    return [_listener_to_dict(l) for l in conn.load_balancer.listeners(**kwargs)]


def create_listener(
    conn: openstack.connection.Connection,
    lb_id: str,
    protocol: str,
    protocol_port: int,
    name: str = "",
    default_pool_id: Optional[str] = None,
) -> dict:
    kwargs: dict = {
        "load_balancer_id": lb_id,
        "protocol": protocol,
        "protocol_port": protocol_port,
    }
    if name:
        kwargs["name"] = name
    if default_pool_id:
        kwargs["default_pool_id"] = default_pool_id
    return _listener_to_dict(conn.load_balancer.create_listener(**kwargs))


def delete_listener(conn: openstack.connection.Connection, listener_id: str) -> None:
    conn.load_balancer.delete_listener(listener_id, ignore_missing=True)


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------

def list_pools(conn: openstack.connection.Connection, lb_id: Optional[str] = None) -> list[dict]:
    kwargs = {}
    if lb_id:
        kwargs["load_balancer_id"] = lb_id
    return [_pool_to_dict(p) for p in conn.load_balancer.pools(**kwargs)]


def create_pool(
    conn: openstack.connection.Connection,
    lb_id: str,
    protocol: str,
    lb_algorithm: str = "ROUND_ROBIN",
    name: str = "",
    listener_id: Optional[str] = None,
) -> dict:
    kwargs: dict = {
        "load_balancer_id": lb_id,
        "protocol": protocol,
        "lb_algorithm": lb_algorithm,
    }
    if name:
        kwargs["name"] = name
    if listener_id:
        kwargs["listener_id"] = listener_id
    return _pool_to_dict(conn.load_balancer.create_pool(**kwargs))


def delete_pool(conn: openstack.connection.Connection, pool_id: str) -> None:
    conn.load_balancer.delete_pool(pool_id, ignore_missing=True)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

def list_members(conn: openstack.connection.Connection, pool_id: str) -> list[dict]:
    return [_member_to_dict(m) for m in conn.load_balancer.members(pool_id)]


def add_member(
    conn: openstack.connection.Connection,
    pool_id: str,
    address: str,
    protocol_port: int,
    subnet_id: Optional[str] = None,
    name: str = "",
    weight: int = 1,
) -> dict:
    kwargs: dict = {
        "address": address,
        "protocol_port": protocol_port,
        "weight": weight,
    }
    if name:
        kwargs["name"] = name
    if subnet_id:
        kwargs["subnet_id"] = subnet_id
    return _member_to_dict(conn.load_balancer.create_member(pool_id, **kwargs))


def remove_member(conn: openstack.connection.Connection, pool_id: str, member_id: str) -> None:
    conn.load_balancer.delete_member(member_id, pool_id, ignore_missing=True)


# ---------------------------------------------------------------------------
# Health Monitors
# ---------------------------------------------------------------------------

def list_health_monitors(conn: openstack.connection.Connection, pool_id: Optional[str] = None) -> list[dict]:
    kwargs = {}
    if pool_id:
        kwargs["pool_id"] = pool_id
    return [_hm_to_dict(hm) for hm in conn.load_balancer.health_monitors(**kwargs)]


def create_health_monitor(
    conn: openstack.connection.Connection,
    pool_id: str,
    type: str = "HTTP",
    delay: int = 5,
    timeout: int = 5,
    max_retries: int = 3,
    name: str = "",
) -> dict:
    kwargs: dict = {
        "pool_id": pool_id,
        "type": type,
        "delay": delay,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    if name:
        kwargs["name"] = name
    return _hm_to_dict(conn.load_balancer.create_health_monitor(**kwargs))


def delete_health_monitor(conn: openstack.connection.Connection, hm_id: str) -> None:
    conn.load_balancer.delete_health_monitor(hm_id, ignore_missing=True)
