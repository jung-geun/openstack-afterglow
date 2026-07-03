"""Ubuntu base normalization and image resolution for layer workflows."""

from __future__ import annotations

UBUNTU_BASE_VALUES = frozenset({"ubuntu-18.04", "ubuntu-20.04", "ubuntu-22.04", "ubuntu-24.04"})
DEFAULT_UBUNTU_BASE = "ubuntu-24.04"
LEGACY_UBUNTU_BASE_ALIASES = {
    "ubuntu-24.04-server-2026-04-15": DEFAULT_UBUNTU_BASE,
}


def normalize_ubuntu_base(value: str | None) -> str:
    """Normalize persisted/requested Ubuntu base metadata to a supported logical key."""
    raw = str(value or "").strip()
    if not raw:
        return DEFAULT_UBUNTU_BASE
    normalized = LEGACY_UBUNTU_BASE_ALIASES.get(raw, raw)
    if normalized not in UBUNTU_BASE_VALUES:
        allowed = ", ".join(sorted(UBUNTU_BASE_VALUES))
        raise ValueError(f"지원하지 않는 Ubuntu base: {value!r} (allowed: {allowed})")
    return normalized


def _setting(settings, name: str) -> str:
    value = getattr(settings, name, "")
    return value.strip() if isinstance(value, str) else ""


def layer_image_id_for_ubuntu_base(settings, ubuntu_base: str | None) -> str:
    """Return the canonical build/runtime image ID for a normalized Ubuntu base.

    Ubuntu 24.04 keeps the legacy fallback chain for compatibility. Non-24.04
    bases must be configured explicitly to avoid silently booting the wrong OS.
    """
    base = normalize_ubuntu_base(ubuntu_base)
    configured = {
        "ubuntu-18.04": _setting(settings, "builder_ubuntu_18_04_image_id"),
        "ubuntu-20.04": _setting(settings, "builder_ubuntu_20_04_image_id"),
        "ubuntu-22.04": _setting(settings, "builder_ubuntu_22_04_image_id"),
        "ubuntu-24.04": _setting(settings, "builder_ubuntu_24_04_image_id"),
    }
    image_id = configured[base]
    if base == DEFAULT_UBUNTU_BASE:
        image_id = image_id or _setting(settings, "builder_image_id") or _setting(settings, "server_image_id")
    if not image_id:
        raise RuntimeError(
            f"{base} 레이어 이미지 ID가 설정되지 않았습니다 (config.toml [builder] ubuntu_*_image_id 필요)"
        )
    return image_id
