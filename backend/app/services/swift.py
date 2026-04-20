"""Swift / Ceph RGW (Object Storage) 서비스 래퍼.

openstacksdk의 conn.object_store 프록시를 사용.
서비스가 없거나 오류 시 빈 목록/기본값을 반환하여 optional 서비스로 동작.

주의: Swift "컨테이너"는 오브젝트 스토리지 버킷을 의미.
Zun "컨테이너"와 혼동 방지를 위해 변수/응답 키에 object_storage_ 접두어 사용.
"""

import logging

_logger = logging.getLogger(__name__)


def list_containers(conn) -> list[dict]:
    """현재 계정의 오브젝트 스토리지 컨테이너(버킷) 목록 반환."""
    try:
        return [
            {
                "name": c.name or "",
                "count": getattr(c, "count", 0) or 0,
                "bytes": getattr(c, "bytes", 0) or 0,
            }
            for c in conn.object_store.containers()
        ]
    except Exception:
        _logger.debug("Swift 컨테이너 목록 조회 실패", exc_info=True)
        return []


def count_containers(conn) -> int:
    """현재 계정의 오브젝트 스토리지 컨테이너 수 반환."""
    try:
        return sum(1 for _ in conn.object_store.containers())
    except Exception:
        return 0


def get_account_metadata(conn) -> dict:
    """현재 계정의 오브젝트 스토리지 사용량 메타데이터 반환.

    반환: {container_count, object_count, bytes_used}
    """
    try:
        meta = conn.object_store.get_account_metadata()
        return {
            "container_count": int(getattr(meta, "account_container_count", 0) or 0),
            "object_count": int(getattr(meta, "account_object_count", 0) or 0),
            "bytes_used": int(getattr(meta, "account_bytes_used", 0) or 0),
        }
    except Exception:
        _logger.debug("Swift 계정 메타데이터 조회 실패", exc_info=True)
        return {"container_count": 0, "object_count": 0, "bytes_used": 0}
