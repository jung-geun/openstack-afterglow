import openstack

from app.models.compute import ImageInfo


def list_images(conn: openstack.connection.Connection) -> list[ImageInfo]:
    images = []
    for img in conn.image.images(status="active"):
        props = img.properties or {}
        os_distro = props.get("os_distro") or _guess_distro(img.name)
        images.append(ImageInfo(
            id=img.id,
            name=img.name,
            status=img.status,
            size=img.size,
            min_disk=img.min_disk or 0,
            min_ram=img.min_ram or 0,
            disk_format=img.disk_format,
            os_type=props.get("os_type"),
            os_distro=os_distro,
            created_at=str(img.created_at) if img.created_at else None,
        ))
    return sorted(images, key=lambda x: x.name)


def _guess_distro(name: str) -> str | None:
    """이미지 이름에서 OS 배포판 추정."""
    lower = name.lower()
    for distro in ("ubuntu", "centos", "rocky", "debian", "fedora", "rhel", "windows", "cirros"):
        if distro in lower:
            return distro
    return None
