import openstack
from typing import Optional

from app.models.storage import VolumeInfo


def create_volume_from_image(
    conn: openstack.connection.Connection,
    name: str,
    image_id: str,
    size_gb: int,
    availability_zone: Optional[str] = None,
) -> VolumeInfo:
    """OS 이미지를 소스로 부트 볼륨 생성."""
    kwargs = {
        "name": name,
        "size": size_gb,
        "imageRef": image_id,
    }
    if availability_zone:
        kwargs["availability_zone"] = availability_zone

    vol = conn.block_storage.create_volume(**kwargs)
    vol = conn.block_storage.wait_for_status(vol, status="available", wait=300)
    return _vol_to_info(vol)


def create_empty_volume(
    conn: openstack.connection.Connection,
    name: str,
    size_gb: int,
    availability_zone: Optional[str] = None,
) -> VolumeInfo:
    """upperdir 용 빈 볼륨 생성."""
    kwargs = {"name": name, "size": size_gb}
    if availability_zone:
        kwargs["availability_zone"] = availability_zone

    vol = conn.block_storage.create_volume(**kwargs)
    vol = conn.block_storage.wait_for_status(vol, status="available", wait=120)
    return _vol_to_info(vol)


def delete_volume(conn: openstack.connection.Connection, volume_id: str) -> None:
    conn.block_storage.delete_volume(volume_id, ignore_missing=True)


def get_volume(conn: openstack.connection.Connection, volume_id: str) -> VolumeInfo:
    vol = conn.block_storage.get_volume(volume_id)
    return _vol_to_info(vol)


def list_volumes(conn: openstack.connection.Connection) -> list[VolumeInfo]:
    return [_vol_to_info(v) for v in conn.block_storage.volumes(details=True)]


def _vol_to_info(vol) -> VolumeInfo:
    return VolumeInfo(
        id=vol.id,
        name=vol.name or "",
        status=vol.status,
        size=vol.size,
        volume_type=vol.volume_type,
        attachments=list(vol.attachments or []),
    )
