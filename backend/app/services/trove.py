"""Trove (Database as a Service) 서비스 래퍼.

openstacksdk의 conn.database 프록시를 사용.
서비스가 없거나 오류 시 빈 목록/0을 반환하여 optional 서비스로 동작.
"""

import logging

_logger = logging.getLogger(__name__)


def list_instances(conn) -> list[dict]:
    """현재 프로젝트의 DB 인스턴스 목록 반환."""
    try:
        results = []
        for i in conn.database.instances():
            flavor = getattr(i, "flavor", {}) or {}
            volume = getattr(i, "volume", {}) or {}
            results.append(
                {
                    "id": i.id,
                    "name": i.name or "",
                    "status": i.status or "",
                    "datastore": getattr(i, "datastore", {}) or {},
                    "flavor_id": flavor.get("id", "") if isinstance(flavor, dict) else "",
                    "size": volume.get("size", 0) if isinstance(volume, dict) else 0,
                    "created_at": str(getattr(i, "created_at", "") or ""),
                }
            )
        return results
    except Exception:
        _logger.debug("Trove 인스턴스 목록 조회 실패", exc_info=True)
        return []


def count_instances(conn) -> int:
    """현재 프로젝트의 DB 인스턴스 수 반환."""
    try:
        return sum(1 for _ in conn.database.instances())
    except Exception:
        return 0
