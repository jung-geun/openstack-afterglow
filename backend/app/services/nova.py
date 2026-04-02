import openstack
from typing import Optional

from app.models.compute import FlavorInfo, InstanceInfo


def list_flavors(conn: openstack.connection.Connection) -> list[FlavorInfo]:
    flavors = []
    for f in conn.compute.flavors(is_public=True):
        extra = dict(f.extra_specs) if f.extra_specs else {}
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
    availability_zone: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> InstanceInfo:
    body = {
        "name": name,
        "flavorRef": flavor_id,
        "networks": [{"uuid": network_id}],
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
    if key_name:
        body["key_name"] = key_name
    if availability_zone:
        body["availability_zone"] = availability_zone
    if metadata:
        body["metadata"] = metadata

    s = conn.compute.create_server(**body)
    s = conn.compute.wait_for_server(s, status="ACTIVE", wait=600)
    return _server_to_info(s)


def delete_server(conn: openstack.connection.Connection, server_id: str) -> None:
    conn.compute.delete_server(server_id, force=True)


def get_console_url(conn: openstack.connection.Connection, server_id: str) -> str:
    s = conn.compute.get_server(server_id)
    result = conn.compute.create_console(s, console_type="novnc")
    return result.get("url", "")


def _server_to_info(s) -> InstanceInfo:
    ips = []
    for net_addrs in (s.addresses or {}).values():
        for addr in net_addrs:
            ips.append(addr["addr"])

    meta = dict(s.metadata) if s.metadata else {}

    image_id = s.image.get("id") if isinstance(s.image, dict) else None
    flavor_id = s.flavor.get("id") if isinstance(s.flavor, dict) else None

    return InstanceInfo(
        id=s.id,
        name=s.name,
        status=s.status,
        image_id=image_id,
        flavor_id=flavor_id,
        ip_addresses=ips,
        created_at=str(s.created_at) if s.created_at else None,
        metadata=meta,
        union_libraries=meta.get("union_libraries", "").split(",") if meta.get("union_libraries") else [],
        union_strategy=meta.get("union_strategy"),
        union_share_ids=meta.get("union_share_ids", "").split(",") if meta.get("union_share_ids") else [],
        union_upper_volume_id=meta.get("union_upper_volume_id"),
    )
