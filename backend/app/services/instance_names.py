from __future__ import annotations

import re
import secrets
from collections.abc import Iterable
from typing import Any

INSTANCE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")

# Lowercase ASCII slug vocabulary. These names flow into Nova, Cinder,
# Manila/CephX-derived labels, and squashfs consume records, so keep them
# boring and resource-name safe.
NAME_ADJECTIVES: tuple[str, ...] = (
    "amber",
    "arc",
    "aurora",
    "binary",
    "brave",
    "bright",
    "calm",
    "cedar",
    "clean",
    "cloud",
    "cobalt",
    "cosmic",
    "crisp",
    "daring",
    "deep",
    "delta",
    "dry",
    "early",
    "elastic",
    "ember",
    "fast",
    "fierce",
    "fresh",
    "frost",
    "gentle",
    "gold",
    "green",
    "hidden",
    "ion",
    "jade",
    "keen",
    "light",
    "lunar",
    "maple",
    "mellow",
    "neon",
    "nimble",
    "nova",
    "onyx",
    "polar",
    "prime",
    "quiet",
    "rapid",
    "red",
    "river",
    "royal",
    "silver",
    "solar",
    "steady",
    "swift",
    "tidal",
    "violet",
    "warm",
    "wild",
    "zen",
)

NAME_NOUNS: tuple[str, ...] = (
    "atlas",
    "beacon",
    "bridge",
    "brook",
    "burst",
    "castle",
    "cipher",
    "comet",
    "coral",
    "crane",
    "dawn",
    "drift",
    "eagle",
    "ember",
    "falcon",
    "field",
    "forge",
    "garden",
    "harbor",
    "haven",
    "island",
    "kernel",
    "lagoon",
    "lantern",
    "matrix",
    "meadow",
    "meteor",
    "mirror",
    "nebula",
    "orbit",
    "packet",
    "pilot",
    "pixel",
    "prairie",
    "quartz",
    "raven",
    "reef",
    "rocket",
    "signal",
    "spark",
    "summit",
    "tensor",
    "thunder",
    "tiger",
    "vertex",
    "voyager",
    "willow",
    "worker",
    "zenith",
)


def normalize_requested_instance_name(value: str | None) -> str | None:
    """Return a user-supplied VM name, or None when the caller wants auto-naming."""

    if value is None:
        return None
    name = value.strip()
    if not name:
        return None
    if not INSTANCE_NAME_RE.match(name):
        raise ValueError("name은 영문자/숫자로 시작하고, 영문자·숫자·하이픈·언더스코어만 허용되며 최대 63자입니다")
    return name


def generate_instance_name() -> str:
    """Generate a lowercase ASCII VM name safe for downstream resource names."""

    return f"{secrets.choice(NAME_ADJECTIVES)}-{secrets.choice(NAME_NOUNS)}-{secrets.token_hex(3)}"


def _server_names(servers: Iterable[Any]) -> set[str]:
    names: set[str] = set()
    for server in servers:
        name = getattr(server, "name", None)
        if name is None and isinstance(server, dict):
            name = server.get("name")
        if name:
            names.add(str(name).lower())
    return names


def existing_instance_names(conn: Any) -> set[str]:
    """List current server names visible in the caller-scoped project."""

    return _server_names(conn.compute.servers(details=True))


def ensure_unique_instance_name(conn: Any, requested_name: str | None, *, max_attempts: int = 128) -> str:
    """Normalize or generate a VM name unique within the scoped OpenStack project."""

    existing = existing_instance_names(conn)
    requested = normalize_requested_instance_name(requested_name)
    if requested is not None:
        if requested.lower() in existing:
            raise ValueError(f"같은 프로젝트에 이미 존재하는 VM 이름입니다: {requested!r}")
        return requested

    for _ in range(max_attempts):
        candidate = generate_instance_name()
        if candidate.lower() not in existing:
            return candidate

    # Extremely defensive fallback if the random vocabulary is exhausted or mocked
    # to collide in tests.
    for _ in range(max_attempts):
        candidate = f"vm-{secrets.token_hex(10)}"
        if candidate.lower() not in existing:
            return candidate

    raise ValueError("중복되지 않는 VM 이름을 생성하지 못했습니다. 잠시 후 다시 시도하세요")
