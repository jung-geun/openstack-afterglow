"""Rate limiting 설정."""

from __future__ import annotations

import ipaddress
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

_logger = logging.getLogger(__name__)


def _trusted_networks() -> list[ipaddress._BaseNetwork]:
    """settings.trusted_proxies 를 IP 네트워크 객체로 파싱. 캐시 안 함 (개수 적음)."""
    from app.config import get_settings

    settings = get_settings()
    raw = getattr(settings, "trusted_proxies", "") or ""
    nets: list[ipaddress._BaseNetwork] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            nets.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            _logger.warning("trusted_proxies 의 잘못된 값 무시: %s", token)
    return nets


def _is_trusted_proxy(ip: str, trusted: list[ipaddress._BaseNetwork]) -> bool:
    if not trusted:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in trusted)


def _get_real_ip(request) -> str:
    """리버스 프록시 환경에서 실제 클라이언트 IP 추출.

    `settings.trusted_proxies` 에 명시된 CIDR 에서 들어온 요청의 X-Forwarded-For /
    X-Real-IP 만 신뢰한다. 그 외에서 들어온 헤더는 위조 가능하므로 무시 — 직접 연결 IP
    사용. 신뢰 목록이 비어 있으면 헤더를 모두 무시 (가장 안전한 기본값).
    """
    direct = get_remote_address(request)
    trusted = _trusted_networks()
    if not _is_trusted_proxy(direct, trusted):
        return direct
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        # 2개 이상이면 rightmost-1 이 HAProxy 가 본 클라이언트 IP, 단일 값이면 그 값
        if len(parts) >= 2:
            return parts[-2]
        if parts:
            return parts[0]
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return direct


limiter = Limiter(key_func=_get_real_ip)
