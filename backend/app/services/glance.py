import openstack

from app.models.compute import ImageInfo


def list_images(conn: openstack.connection.Connection) -> list[ImageInfo]:
    images = []
    for img in conn.image.images(status="active"):
        images.append(ImageInfo(
            id=img.id,
            name=img.name,
            status=img.status,
            size=img.size,
            min_disk=img.min_disk or 0,
            min_ram=img.min_ram or 0,
            disk_format=img.disk_format,
            os_type=img.properties.get("os_type") if img.properties else None,
            created_at=str(img.created_at) if img.created_at else None,
        ))
    return sorted(images, key=lambda x: x.name)
