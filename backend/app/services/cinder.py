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


def get_volume_limits(conn: openstack.connection.Connection) -> dict:
    """프로젝트의 Cinder 리소스 사용량/한도 조회."""
    limits = conn.block_storage.get_limits()
    a = limits.absolute
    return {
        "volumes_used": getattr(a, 'total_volumes_used', 0),
        "volumes_limit": getattr(a, 'max_total_volumes', -1),
        "gigabytes_used": getattr(a, 'total_gigabytes_used', 0),
        "gigabytes_limit": getattr(a, 'max_total_volume_gigabytes', -1),
    }


def get_volume_image_metadata(conn: openstack.connection.Connection, volume_id: str) -> dict | None:
    """부트 볼륨의 원본 이미지 메타데이터 반환 (volume_image_metadata 필드)."""
    try:
        vol = conn.block_storage.get_volume(volume_id)
        raw = vol.to_dict() if hasattr(vol, 'to_dict') else {}
        return raw.get('volume_image_metadata') or getattr(vol, 'volume_image_metadata', None)
    except Exception:
        return None


def _vol_to_info(vol) -> VolumeInfo:
    return VolumeInfo(
        id=vol.id,
        name=vol.name or "",
        status=vol.status,
        size=vol.size,
        volume_type=vol.volume_type,
        attachments=list(vol.attachments or []),
    )
