import openstack

from app.models.compute import ImageInfo, ImageDetail


def list_images(conn: openstack.connection.Connection, project_id: str | None = None) -> list[ImageInfo]:
    seen: set[str] = set()
    images: list[ImageInfo] = []

    def _add(img) -> None:
        if img.id in seen:
            return
        seen.add(img.id)
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
            owner=getattr(img, 'owner', None) or getattr(img, 'project_id', None),
            visibility=getattr(img, 'visibility', None),
        ))

    # public, community, shared: 접근 가능한 공개/공유 이미지
    for vis in ("public", "community", "shared"):
        try:
            for img in conn.image.images(status="active", visibility=vis):
                _add(img)
        except Exception:
            pass

    # 현재 프로젝트의 private 이미지만
    pid = project_id or getattr(conn, '_union_project_id', None)
    try:
        kwargs = {"status": "active", "visibility": "private"}
        if pid:
            kwargs["owner"] = pid
        for img in conn.image.images(**kwargs):
            _add(img)
    except Exception:
        pass

    return sorted(images, key=lambda x: x.name)


def get_image(conn: openstack.connection.Connection, image_id: str) -> ImageDetail:
    img = conn.image.get_image(image_id)
    props = img.properties or {}
    os_distro = props.get("os_distro") or _guess_distro(img.name)
    # properties에서 내부 키 제외하고 반환
    _exclude = {"os_distro", "os_type"}
    clean_props = {k: v for k, v in props.items() if k not in _exclude}
    return ImageDetail(
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
        owner=getattr(img, 'owner', None) or getattr(img, 'project_id', None),
        visibility=getattr(img, 'visibility', None),
        checksum=getattr(img, 'checksum', None),
        container_format=img.container_format,
        virtual_size=getattr(img, 'virtual_size', None),
        updated_at=str(img.updated_at) if getattr(img, 'updated_at', None) else None,
        protected=getattr(img, 'is_protected', False) or False,
        tags=list(getattr(img, 'tags', None) or []),
        properties=clean_props,
    )


def delete_image(conn: openstack.connection.Connection, image_id: str) -> None:
    conn.image.delete_image(image_id, ignore_missing=False)


def update_image_metadata(
    conn: openstack.connection.Connection,
    image_id: str,
    name: str | None = None,
    os_distro: str | None = None,
    os_type: str | None = None,
    min_disk: int | None = None,
    min_ram: int | None = None,
    visibility: str | None = None,
) -> ImageInfo:
    """이미지 메타데이터 업데이트 (소유한 이미지만 가능)."""
    kwargs: dict = {}
    if name is not None:
        kwargs["name"] = name
    if os_distro is not None:
        kwargs["os_distro"] = os_distro
    if os_type is not None:
        kwargs["os_type"] = os_type
    if min_disk is not None:
        kwargs["min_disk"] = min_disk
    if min_ram is not None:
        kwargs["min_ram"] = min_ram
    if visibility is not None:
        kwargs["visibility"] = visibility
    img = conn.image.update_image(image_id, **kwargs)
    props = img.properties or {}
    od = props.get("os_distro") or _guess_distro(img.name)
    return ImageInfo(
        id=img.id,
        name=img.name,
        status=img.status,
        size=img.size,
        min_disk=img.min_disk or 0,
        min_ram=img.min_ram or 0,
        disk_format=img.disk_format,
        os_type=props.get("os_type"),
        os_distro=od,
        created_at=str(img.created_at) if img.created_at else None,
        owner=getattr(img, 'owner', None) or getattr(img, 'project_id', None),
    )


def _guess_distro(name: str) -> str | None:
    """이미지 이름에서 OS 배포판 추정."""
    lower = name.lower()
    for distro in ("ubuntu", "centos", "rocky", "debian", "fedora", "rhel", "windows", "cirros"):
        if distro in lower:
            return distro
    return None
