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
