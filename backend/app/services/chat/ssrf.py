"""SSRF 방어 — 커스텀 HTTP 툴이 호출할 URL 을 백엔드가 대리 요청하기 전 검증.

차단 대상:
- http/https 이외 스킴
- 사설(10/8·172.16/12·192.168/16·fc00::/7), 루프백(127/8·::1),
  링크로컬(169.254/16 — 클라우드 메타데이터 169.254.169.254 포함, fe80::/10),
  멀티캐스트·예약·unspecified IP
- 위험 호스트명(localhost, metadata.* 등)

호스트명은 DNS 해석 후 **모든** 결과 IP 를 검사한다(하나라도 내부면 차단).
⚠️ 한계: 해석 후 httpx 가 재해석하므로 DNS rebinding 완전 차단은 아님(내부 도구용, 문서화된 트레이드오프).
DNS 해석은 블로킹이므로 호출부가 asyncio.to_thread 로 감싼다.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal"}


class SsrfBlocked(ValueError):
    """SSRF 정책 위반 — 요청 거부."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified


def validate_url(url: str) -> str:
    """URL 이 SSRF 정책을 통과하면 그대로 반환, 아니면 SsrfBlocked. (블로킹 — to_thread 로 호출)"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SsrfBlocked("http/https 스킴만 허용됩니다")
    host = parsed.hostname
    if not host:
        raise SsrfBlocked("호스트가 없습니다")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise SsrfBlocked(f"차단된 호스트: {host}")

    # IP 리터럴이면 바로 검사
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if _is_blocked_ip(ip):
            raise SsrfBlocked("내부/사설 IP 는 차단됩니다")
        return url

    # 호스트명 → DNS 해석 후 모든 IP 검사
    try:
        infos = socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise SsrfBlocked("호스트를 확인할 수 없습니다") from exc
    if not infos:
        raise SsrfBlocked("호스트를 확인할 수 없습니다")
    for info in infos:
        addr = info[4][0]
        try:
            resolved = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(resolved):
            raise SsrfBlocked("내부/사설 IP 로 해석되는 호스트는 차단됩니다")
    return url
