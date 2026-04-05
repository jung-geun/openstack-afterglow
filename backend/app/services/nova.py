import openstack
from typing import Optional

from app.models.compute import FlavorInfo, InstanceInfo, IpAddress


def list_flavors(conn: openstack.connection.Connection) -> list[FlavorInfo]:
    flavors = []
    for f in conn.compute.flavors(is_public=True):
        extra = dict(f.extra_specs) if f.extra_specs else {}
        # List API는 extra_specs를 포함하지 않을 수 있으므로 개별 조회 fallback
        if not extra:
            try:
                detail = conn.compute.get_flavor(f.id)
                extra = dict(detail.extra_specs) if detail.extra_specs else {}
            except Exception:
                pass
        flavors.append(FlavorInfo(
            id=f.id,
            name=f.name,
            vcpus=f.vcpus,
            ram=f.ram,
            disk=f.disk,
            is_public=True,
            extra_specs=extra,
        ))
    return sorted(flavors, key=lambda x: (x.vcpus, x.ram))


def list_servers(conn: openstack.connection.Connection) -> list[InstanceInfo]:
    servers = []
    for s in conn.compute.servers(details=True):
        servers.append(_server_to_info(s))
    return servers


def get_server(conn: openstack.connection.Connection, server_id: str) -> InstanceInfo:
    s = conn.compute.get_server(server_id)
    return _server_to_info(s)


def create_server(
    conn: openstack.connection.Connection,
    name: str,
    flavor_id: str,
    network_id: str,
    boot_volume_id: str,
    userdata: str,
    key_name: Optional[str] = None,
    admin_pass: Optional[str] = None,
    availability_zone: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> InstanceInfo:
    body = {
        "name": name,
        "flavorRef": flavor_id,
        "block_device_mapping_v2": [
            {
                "boot_index": 0,
                "uuid": boot_volume_id,
                "source_type": "volume",
                "destination_type": "volume",
                "delete_on_termination": True,
            }
        ],
        "user_data": userdata,
    }
    # network_id가 있으면 지정, 없으면 자동 할당
    if network_id:
        body["networks"] = [{"uuid": network_id}]
    if key_name:
        body["key_name"] = key_name
    if admin_pass:
        body["adminPass"] = admin_pass
    if availability_zone:
        body["availability_zone"] = availability_zone
    if metadata:
        body["metadata"] = metadata

    s = conn.compute.create_server(**body)
    s = conn.compute.wait_for_server(s, status="ACTIVE", wait=600)
    return _server_to_info(s)


def get_console_output(conn: openstack.connection.Connection, server_id: str, length: int = 100) -> str:
    output = conn.compute.get_server_console_output(server_id, length=length)
    return output.get("output", "")


def list_volume_attachments(conn: openstack.connection.Connection, server_id: str) -> list[dict]:
    return [
        {"id": a.id, "volume_id": a.volume_id, "device": a.device, "server_id": a.server_id}
        for a in conn.compute.volume_attachments(server_id)
    ]


def attach_volume(conn: openstack.connection.Connection, server_id: str, volume_id: str) -> dict:
    a = conn.compute.create_volume_attachment(server_id, volume_id=volume_id)
    return {"id": a.id, "volume_id": a.volume_id, "device": a.device}


def detach_volume(conn: openstack.connection.Connection, server_id: str, volume_id: str) -> None:
    conn.compute.delete_volume_attachment(volume_id, server_id)


def attach_interface(conn: openstack.connection.Connection, server_id: str, net_id: str) -> dict:
    iface = conn.compute.create_server_interface(server_id, net_id=net_id)
    return {
        "port_id": iface.port_id,
        "net_id": iface.net_id,
        "fixed_ips": iface.fixed_ips or [],
    }


def detach_interface(conn: openstack.connection.Connection, server_id: str, port_id: str) -> None:
    conn.compute.delete_server_interface(port_id, server=server_id)


def get_project_limits(conn: openstack.connection.Connection) -> dict:
    """프로젝트의 Nova 리소스 사용량/한도 조회."""
    limits = conn.compute.get_limits()
    a = limits.absolute
    return {
        "instances_used": getattr(a, 'total_instances_used', 0),
        "instances_limit": getattr(a, 'max_total_instances', -1),
        "vcpus_used": getattr(a, 'total_cores_used', 0),
        "vcpus_limit": getattr(a, 'max_total_cores', -1),
        "ram_used_mb": getattr(a, 'total_ram_used', 0),
        "ram_limit_mb": getattr(a, 'max_total_ram_size', -1),
    }


def list_keypairs(conn: openstack.connection.Connection) -> list[dict]:
    return [
        {"name": kp.name, "fingerprint": kp.fingerprint, "type": getattr(kp, 'type', 'ssh')}
        for kp in conn.compute.keypairs()
    ]


def create_keypair(
    conn: openstack.connection.Connection,
    name: str,
    public_key: Optional[str] = None,
    key_type: str = "ssh",
) -> dict:
    """키페어 생성. public_key가 없으면 Nova가 자동 생성하고 private_key를 반환."""
    body: dict = {"name": name, "type": key_type}
    if public_key:
        body["public_key"] = public_key
    kp = conn.compute.create_keypair(**body)
    return {
        "name": kp.name,
        "fingerprint": kp.fingerprint,
        "type": getattr(kp, 'type', 'ssh'),
        "public_key": getattr(kp, 'public_key', None),
        "private_key": getattr(kp, 'private_key', None),
    }


def delete_keypair(conn: openstack.connection.Connection, name: str) -> None:
    conn.compute.delete_keypair(name, ignore_missing=True)


def delete_server(conn: openstack.connection.Connection, server_id: str) -> None:
    conn.compute.delete_server(server_id, force=True)


def start_server(conn: openstack.connection.Connection, server_id: str) -> None:
    conn.compute.start_server(server_id)


def stop_server(conn: openstack.connection.Connection, server_id: str) -> None:
    conn.compute.stop_server(server_id)


def reboot_server(conn: openstack.connection.Connection, server_id: str, reboot_type: str = "SOFT") -> None:
    conn.compute.reboot_server(server_id, reboot_type)


def get_console_url(conn: openstack.connection.Connection, server_id: str) -> str:
    s = conn.compute.get_server(server_id)
    result = conn.compute.create_console(s, console_type="novnc")
    return result.get("url", "")


def _server_to_info(s) -> InstanceInfo:
    ips = []
    for net_name, net_addrs in (s.addresses or {}).items():
        for addr in net_addrs:
            ips.append(IpAddress(
                addr=addr["addr"],
                type=addr.get("OS-EXT-IPS:type", "fixed"),
                network_name=net_name,
            ))

    meta = dict(s.metadata) if s.metadata else {}

    image_id = s.image.get("id") if isinstance(s.image, dict) else None
    flavor_id = None
    flavor_name = None
    if isinstance(s.flavor, dict):
        flavor_id = s.flavor.get("id")
        # 마이크로버전 2.47+에서는 "id" 없이 "original_name"만 반환
        flavor_name = s.flavor.get("original_name")

    return InstanceInfo(
        id=s.id,
        name=s.name,
        status=s.status,
        image_id=image_id,
        flavor_id=flavor_id,
        flavor_name=flavor_name,
        ip_addresses=ips,
        created_at=str(s.created_at) if s.created_at else None,
        metadata=meta,
        union_libraries=meta.get("union_libraries", "").split(",") if meta.get("union_libraries") else [],
        union_strategy=meta.get("union_strategy"),
        union_share_ids=meta.get("union_share_ids", "").split(",") if meta.get("union_share_ids") else [],
        union_upper_volume_id=meta.get("union_upper_volume_id"),
        key_name=getattr(s, 'key_name', None),
        user_id=getattr(s, 'user_id', None),
    )
