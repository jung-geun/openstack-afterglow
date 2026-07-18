"""빌트인 AI 채팅 사용량 집계 — chat_usage_logs 원장에서 사용자별 요약.

(구 LibreChat MongoDB 미러링을 대체.) 저장소 장애 시에도 found=False 로 안전 반환(항상 200).
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.database import get_session_factory, is_db_available
from app.models.chat_db import ChatUsageLog

logger = logging.getLogger(__name__)

_EMPTY = {
    "found": False,
    "total_credited_cost": 0.0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "request_count": 0,
}


async def user_usage_summary(user_id: str, project_id: str) -> dict:
    """로그인 사용자 본인의 누적 사용량(크레딧·토큰·요청 수). 실패 시 빈 요약(found=False)."""
    if not is_db_available():
        return dict(_EMPTY)
    factory = get_session_factory()
    if factory is None:
        return dict(_EMPTY)
    try:
        async with factory() as session:
            stmt = select(
                func.coalesce(func.sum(ChatUsageLog.credited_cost), 0),
                func.coalesce(func.sum(ChatUsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(ChatUsageLog.completion_tokens), 0),
                func.count(ChatUsageLog.id),
            ).where(ChatUsageLog.user_id == user_id, ChatUsageLog.project_id == project_id)
            row = (await session.execute(stmt)).one()
        credited, pt, ct, count = row
        return {
            "found": count > 0,
            "total_credited_cost": float(credited or 0),
            "prompt_tokens": int(pt or 0),
            "completion_tokens": int(ct or 0),
            "request_count": int(count or 0),
        }
    except Exception:
        logger.warning("빌트인 채팅 사용량 집계 실패", exc_info=True)
        return dict(_EMPTY)
