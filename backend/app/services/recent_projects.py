"""사용자별 최근 접근 프로젝트 추적 (Redis Sorted Set).

키 스킴: afterglow:recent_projects:{user_id}
score: epoch ms (높을수록 최근)
TTL: 30일
"""

from __future__ import annotations

import time

from app.services.cache import _get_redis

_PREFIX = "afterglow:recent_projects:"
_TTL = 30 * 24 * 3600  # 30일


def _key(user_id: str) -> str:
    return f"{_PREFIX}{user_id}"


async def record_project_access(user_id: str, project_id: str) -> None:
    """사용자의 프로젝트 접근 시각을 기록 (best-effort)."""
    if not user_id or not project_id:
        return
    try:
        r = await _get_redis()
        now_ms = int(time.time() * 1000)
        await r.zadd(_key(user_id), {project_id: now_ms})
        await r.expire(_key(user_id), _TTL)
    except Exception:
        pass


async def get_recent_project_ids(user_id: str) -> list[tuple[str, int]]:
    """최근 접근 프로젝트 ID 목록 반환 [(project_id, epoch_ms), ...] 최신순."""
    try:
        r = await _get_redis()
        items = await r.zrevrange(_key(user_id), 0, -1, withscores=True)
        return [(pid.decode() if isinstance(pid, bytes) else pid, int(score)) for pid, score in items]
    except Exception:
        return []
