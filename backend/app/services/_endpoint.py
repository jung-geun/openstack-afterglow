"""OpenStack endpoint URL 정규화 공통 헬퍼."""

import re

# 마지막 path segment가 /vN 또는 /vN.M 형태(version path)인지 검사
_HAS_VERSION_RE = re.compile(r"/v[0-9]+(?:\.[0-9]+)?$")


def normalize_keystone_url(url: str) -> str:
    """Keystone auth_url 정규화 — 사용자 입력 존중 + v3 자동 부착.

    - 빈 문자열: 그대로 통과 (미설정 호환)
    - trailing slash 제거
    - 끝 segment가 /vN 또는 /vN.M 이면 그대로 둔다 (사용자가 명시한 endpoint 존중)
    - version path가 없으면 /v3 부착
    """
    if not url or not url.strip():
        return url
    s = url.strip().rstrip("/")
    if _HAS_VERSION_RE.search(s):
        return s
    return f"{s}/v3"


def normalize_endpoint(url: str) -> str:
    """일반 OpenStack endpoint URL: trailing slash만 제거."""
    if not url or not url.strip():
        return url
    return url.strip().rstrip("/")
