"""Rate limiting 설정."""
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_real_ip(request) -> str:
    """리버스 프록시 환경에서 실제 클라이언트 IP 추출.
    X-Forwarded-For → X-Real-IP → 직접 연결 IP 순으로 시도.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_real_ip)
