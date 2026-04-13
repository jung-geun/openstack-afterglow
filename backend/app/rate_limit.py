"""Rate limiting 설정."""
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_real_ip(request) -> str:
    """리버스 프록시 환경에서 실제 클라이언트 IP 추출.

    단일 HAProxy 프록시 뒤에 위치하는 구조를 가정.
    X-Forwarded-For 헤더의 마지막 값은 HAProxy가 추가한 것이므로 신뢰할 수 있고,
    그 앞 값이 실제 클라이언트 IP다.
    헤더가 없거나 단일 값이면 직접 연결 IP 또는 X-Real-IP를 사용.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",")]
        # 2개 이상이면 rightmost-1이 HAProxy가 본 클라이언트 IP
        if len(parts) >= 2:
            return parts[-2]
        # 단일 값이면 HAProxy가 추가한 클라이언트 IP
        return parts[0]
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_real_ip)
