"""
Redis sorted set 기반 경량 시계열 저장소.

key:   union:ts:{resource_type}
score: Unix timestamp (float)
member: JSON 문자열 {"ts": float, ...데이터...}

범위 파라미터: "1d" | "2d" | "7d" | "30d"
"""

import json
import logging
import time
from typing import Any

_logger = logging.getLogger(__name__)

_RANGE_SECONDS: dict[str, int] = {
    "1d":  86_400,
    "2d":  172_800,
    "7d":  604_800,
    "30d": 2_592_000,
}


async def record_snapshot(resource_type: str, data: dict[str, Any]) -> None:
    """현재 시각으로 스냅샷 저장."""
    from app.services.cache import _get_redis
    try:
        r = await _get_redis()
        ts = time.time()
        member = json.dumps({"ts": ts, **data})
        key = f"union:ts:{resource_type}"
        await r.zadd(key, {member: ts})
        # 90일보다 오래된 항목 자동 삭제
        cutoff = ts - 90 * 86_400
        await r.zremrangebyscore(key, "-inf", cutoff)
    except Exception:
        _logger.warning("시계열 스냅샷 저장 실패 (resource_type=%s)", resource_type, exc_info=True)


async def get_timeseries(resource_type: str, range_str: str = "7d") -> list[dict]:
    """기간별 스냅샷 목록 반환. Redis 오류 시 빈 목록 반환."""
    from app.services.cache import _get_redis
    seconds = _RANGE_SECONDS.get(range_str, _RANGE_SECONDS["7d"])
    try:
        r = await _get_redis()
        key = f"union:ts:{resource_type}"
        now = time.time()
        start = now - seconds
        raw_items = await r.zrangebyscore(key, start, "+inf")
        result = []
        for raw in raw_items:
            try:
                result.append(json.loads(raw))
            except Exception:
                pass
        return result
    except Exception:
        _logger.warning("시계열 조회 실패 (resource_type=%s)", resource_type, exc_info=True)
        return []
