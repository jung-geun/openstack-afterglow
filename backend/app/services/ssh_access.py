from __future__ import annotations

import re

_GITHUB_USERNAME_RE = re.compile(r"^(?!-)(?!.*--)[A-Za-z0-9-]{1,39}(?<!-)\Z")


def normalize_github_username(value: str | None) -> str | None:
    """Return a validated GitHub username suitable for cloud-init's gh: source."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not _GITHUB_USERNAME_RE.match(normalized):
        raise ValueError(
            "github_username은 1~39자의 영문자, 숫자, 하이픈만 사용할 수 있으며 하이픈으로 시작·종료하거나 연속 하이픈을 사용할 수 없습니다"
        )
    return normalized
