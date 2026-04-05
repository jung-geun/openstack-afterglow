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


def get_volume_quota(conn: openstack.connection.Connection, project_id: str) -> dict:
    """프로젝트의 상세 Cinder 할당량 (usage 포함)."""
    def _extract(q):
        if q is None:
            return {"limit": -1, "in_use": 0}
        if isinstance(q, dict):
            return {"limit": q.get("limit", -1), "in_use": q.get("in_use", 0)}
        return {"limit": getattr(q, "limit", -1), "in_use": getattr(q, "in_use", 0)}

    try:
        quota = conn.block_storage.get_quota_set(project_id, usage=True)
        return {
            "volumes": _extract(getattr(quota, "volumes", None)),
            "snapshots": _extract(getattr(quota, "snapshots", None)),
            "gigabytes": _extract(getattr(quota, "gigabytes", None)),
            "backups": _extract(getattr(quota, "backups", None)),
            "backup_gigabytes": _extract(getattr(quota, "backup_gigabytes", None)),
        }
    except Exception:
        # fallback: limits API
        limits = conn.block_storage.get_limits()
        a = limits.absolute
        return {
            "volumes": {"limit": getattr(a, 'max_total_volumes', -1), "in_use": getattr(a, 'total_volumes_used', 0)},
            "snapshots": {"limit": getattr(a, 'max_total_snapshots', -1), "in_use": getattr(a, 'total_snapshots_used', 0)},
            "gigabytes": {"limit": getattr(a, 'max_total_volume_gigabytes', -1), "in_use": getattr(a, 'total_gigabytes_used', 0)},
            "backups": {"limit": getattr(a, 'max_total_backups', -1), "in_use": getattr(a, 'total_backups_used', 0)},
            "backup_gigabytes": {"limit": getattr(a, 'max_total_backup_gigabytes', -1), "in_use": getattr(a, 'total_backup_gigabytes_used', 0)},
        }


def get_volume_image_metadata(conn: openstack.connection.Connection, volume_id: str) -> dict | None:
    """부트 볼륨의 원본 이미지 메타데이터 반환 (volume_image_metadata 필드)."""
    try:
        vol = conn.block_storage.get_volume(volume_id)
        raw = vol.to_dict() if hasattr(vol, 'to_dict') else {}
        return raw.get('volume_image_metadata') or getattr(vol, 'volume_image_metadata', None)
    except Exception:
        return None


def list_backups(conn: openstack.connection.Connection) -> list[dict]:
    return [_backup_to_dict(b) for b in conn.block_storage.backups(details=True)]


def get_backup(conn: openstack.connection.Connection, backup_id: str) -> dict:
    b = conn.block_storage.get_backup(backup_id)
    return _backup_to_dict(b)


def create_backup(
    conn: openstack.connection.Connection,
    volume_id: str,
    name: str,
    description: Optional[str] = None,
    incremental: bool = False,
) -> dict:
    kwargs: dict = {"volume_id": volume_id, "name": name, "is_incremental": incremental}
    if description:
        kwargs["description"] = description
    b = conn.block_storage.create_backup(**kwargs)
    return _backup_to_dict(b)


def delete_backup(conn: openstack.connection.Connection, backup_id: str) -> None:
    conn.block_storage.delete_backup(backup_id, ignore_missing=True)


def restore_backup(conn: openstack.connection.Connection, backup_id: str, volume_id: Optional[str] = None) -> dict:
    kwargs: dict = {}
    if volume_id:
        kwargs["volume_id"] = volume_id
    result = conn.block_storage.restore_backup(backup_id, **kwargs)
    return {"volume_id": getattr(result, 'volume_id', None), "volume_name": getattr(result, 'volume_name', None)}


def _backup_to_dict(b) -> dict:
    return {
        "id": b.id,
        "name": b.name or "",
        "status": b.status,
        "volume_id": b.volume_id,
        "size": b.size,
        "is_incremental": getattr(b, 'is_incremental', False),
        "description": b.description or "",
        "created_at": str(b.created_at) if getattr(b, 'created_at', None) else None,
    }


def _vol_to_info(vol) -> VolumeInfo:
    return VolumeInfo(
        id=vol.id,
        name=vol.name or "",
        status=vol.status,
        size=vol.size,
        volume_type=vol.volume_type,
        attachments=list(vol.attachments or []),
    )
