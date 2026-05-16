"""TTL 카테고리.

v1 은 단순 4-티어 TTL (fast/normal/slow/static) 를 사용한다.
Phase B 에서 dynamic TTL (mutcount 기반) 과 3-tier 시스템으로 확장 예정.
"""

from app.config import get_settings


def ttl_fast() -> int:
    """빈번히 변하는 리소스 TTL (인스턴스, 볼륨, 플로팅IP 등)."""
    return get_settings().cache_ttl_fast


def ttl_normal() -> int:
    """일반 리소스 TTL (네트워크, 라우터, 토폴로지 등)."""
    return get_settings().cache_ttl_normal


def ttl_slow() -> int:
    """느리게 변하는 리소스 TTL (키페어, 보안그룹 등)."""
    return get_settings().cache_ttl_slow


def ttl_static() -> int:
    """거의 변하지 않는 리소스 TTL (이미지, 플레이버 등)."""
    return get_settings().cache_ttl_static
