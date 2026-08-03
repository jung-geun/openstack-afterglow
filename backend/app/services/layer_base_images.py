"""Glance base-image validation for squashfs layer workflows."""

from __future__ import annotations

import re
from typing import Any

from app.services.layer_ubuntu import normalize_ubuntu_base

IMAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NAME_UBUNTU_RE = re.compile(r"ubuntu[^0-9]*(18\.04|20\.04|22\.04|24\.04)", re.IGNORECASE)
_SUPPORTED_RELEASES = {"18.04", "20.04", "22.04", "24.04"}


def _attr(img: Any, name: str, default: Any = None) -> Any:
    if isinstance(img, dict):
        if name in img:
            return img.get(name)
        props = img.get("properties")
        if isinstance(props, dict):
            return props.get(name, default)
        return default
    if hasattr(img, name):
        return getattr(img, name)
    try:
        return img[name]
    except Exception:
        pass
    props = getattr(img, "properties", None)
    if isinstance(props, dict):
        return props.get(name, default)
    to_dict = getattr(img, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, dict):
            if name in data:
                return data.get(name)
            props = data.get("properties")
            if isinstance(props, dict):
                return props.get(name, default)
    return default


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _release_to_base(value: Any) -> str | None:
    raw = _string(value)
    if not raw:
        return None
    lowered = raw.lower().strip()
    if lowered.startswith("ubuntu-"):
        try:
            return normalize_ubuntu_base(lowered)
        except ValueError:
            return None
    match = re.search(r"(18\.04|20\.04|22\.04|24\.04)", lowered)
    if not match:
        return None
    release = match.group(1)
    if release not in _SUPPORTED_RELEASES:
        return None
    return normalize_ubuntu_base(f"ubuntu-{release}")


def ubuntu_base_from_image(img: Any) -> str | None:
    """Infer supported Ubuntu base from Glance metadata, then safe image name."""
    distro = (_string(_attr(img, "os_distro")) or _string(_attr(img, "distro")) or "").lower()
    if distro == "ubuntu":
        for key in ("os_version", "os_version_id", "release", "ubuntu_base"):
            base = _release_to_base(_attr(img, key))
            if base:
                return base

    name = _string(_attr(img, "name")) or ""
    match = _NAME_UBUNTU_RE.search(name)
    if not match:
        return None
    return normalize_ubuntu_base(f"ubuntu-{match.group(1)}")


def snapshot_from_image(img: Any) -> dict:
    """Return persisted base image fingerprint/display metadata."""
    ubuntu_base = ubuntu_base_from_image(img)
    image_id = _string(_attr(img, "id")) or _string(_attr(img, "image_id"))
    return {
        "base_image_id": image_id,
        "base_image_name": _string(_attr(img, "name")),
        "base_image_checksum": _string(_attr(img, "checksum")),
        "base_image_os_hash_algo": _string(_attr(img, "os_hash_algo")),
        "base_image_os_hash_value": _string(_attr(img, "os_hash_value")),
        "base_image_min_disk": _int(_attr(img, "min_disk")),
        "base_image_visibility": _string(_attr(img, "visibility")),
        "base_image_owner": _string(_attr(img, "owner")),
        "ubuntu_base": ubuntu_base,
        "source_metadata": {"base_image_source": "glance"},
    }


def validate_base_image_id(base_image_id: str) -> str:
    value = str(base_image_id or "").strip()
    if not IMAGE_ID_RE.match(value):
        raise ValueError("base_image_id 형식이 유효하지 않습니다")
    return value


def resolve_base_image_snapshot(conn: Any, base_image_id: str, expected_ubuntu_base: str | None = None) -> dict:
    """Fetch and validate an active supported Ubuntu Glance image."""
    image_id = validate_base_image_id(base_image_id)
    img = conn.image.get_image(image_id)
    if img is None:
        raise ValueError("base_image_id에 해당하는 Glance 이미지를 찾을 수 없습니다")
    status = (_string(_attr(img, "status")) or "").lower()
    if status != "active":
        raise ValueError(f"Glance 이미지는 active 상태여야 합니다 (현재: {status or 'unknown'})")
    snapshot = snapshot_from_image(img)
    ubuntu_base = snapshot.get("ubuntu_base")
    if not ubuntu_base:
        raise ValueError("지원하는 Ubuntu 18.04/20.04/22.04/24.04 이미지가 아닙니다")
    if expected_ubuntu_base is not None and normalize_ubuntu_base(expected_ubuntu_base) != ubuntu_base:
        raise ValueError(f"선택한 이미지의 Ubuntu base가 요청과 일치하지 않습니다: {ubuntu_base}")
    snapshot["base_image_id"] = image_id
    return snapshot


def legacy_snapshot_for_ubuntu_base(settings: Any, ubuntu_base: str | None) -> dict:
    """Reject legacy rows until the one-time importer records their exact image."""
    base = normalize_ubuntu_base(ubuntu_base)
    raise RuntimeError(
        f"legacy layer artifact for {base} has no base-image snapshot; "
        "run import_runtime_infrastructure_settings.py --legacy-base-image before consuming it"
    )
