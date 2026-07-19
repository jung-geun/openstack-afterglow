"""빌트인 AI 채팅 관리자 통계 — chat_usage_logs 원장 집계.

전체 시스템(+프로젝트 필터) 사용량을 사용자별·모델별·월별·전체로 집계한다.
저장소 장애 시에도 빈 집계로 안전 반환(통계는 부가 화면 — 대시보드를 막지 않는다).

⚠️ source 규칙:
- overview/by_model/monthly 는 모든 source(web/api/system)를 합산 — 시스템 원가까지 추적.
- by_user 는 source="system"(제목 요약 등 시스템 부담)을 제외 — 사용자 실사용만 표기.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.database import get_session_factory, is_db_available
from app.models.chat_db import ChatUsageLog

logger = logging.getLogger(__name__)

_RANGE_DAYS = {"30d": 30, "90d": 90, "1y": 365}


def _cutoff(range_key: str) -> datetime | None:
    """range → created_at 하한. 'all'/미지정은 None(전체)."""
    days = _RANGE_DAYS.get(range_key)
    if days is None:
        return None
    return datetime.now(UTC) - timedelta(days=days)


def _base_conds(range_key: str, project_id: str | None):
    conds = []
    cutoff = _cutoff(range_key)
    if cutoff is not None:
        conds.append(ChatUsageLog.created_at >= cutoff)
    if project_id:
        conds.append(ChatUsageLog.project_id == project_id)
    return conds


def _factory():
    if not is_db_available():
        return None
    return get_session_factory()


_OVERVIEW_EMPTY = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "credited_cost": 0.0,
    "raw_cost": 0.0,
    "request_count": 0,
    "active_users": 0,
    "conversation_count": 0,
    "by_source": [],
}


async def overview(range_key: str = "all", project_id: str | None = None) -> dict:
    """전체 요약 KPI + source(web/api/system) 분해."""
    factory = _factory()
    if factory is None:
        return dict(_OVERVIEW_EMPTY)
    conds = _base_conds(range_key, project_id)
    try:
        async with factory() as session:
            totals = (
                await session.execute(
                    select(
                        func.coalesce(func.sum(ChatUsageLog.prompt_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.completion_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.credited_cost), 0),
                        func.coalesce(func.sum(ChatUsageLog.raw_cost), 0),
                        func.count(ChatUsageLog.id),
                        func.count(func.distinct(ChatUsageLog.user_id)),
                        func.count(func.distinct(ChatUsageLog.conversation_id)),
                    ).where(*conds)
                )
            ).one()
            src_rows = (
                await session.execute(
                    select(
                        ChatUsageLog.source,
                        func.coalesce(func.sum(ChatUsageLog.prompt_tokens + ChatUsageLog.completion_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.raw_cost), 0),
                        func.count(ChatUsageLog.id),
                    )
                    .where(*conds)
                    .group_by(ChatUsageLog.source)
                )
            ).all()
        pt, ct, credited, raw, req, users, convs = totals
        return {
            "prompt_tokens": int(pt or 0),
            "completion_tokens": int(ct or 0),
            "total_tokens": int(pt or 0) + int(ct or 0),
            "credited_cost": float(credited or 0),
            "raw_cost": float(raw or 0),
            "request_count": int(req or 0),
            "active_users": int(users or 0),
            "conversation_count": int(convs or 0),
            "by_source": [
                {"source": s or "web", "tokens": int(t or 0), "raw_cost": float(r or 0), "request_count": int(c or 0)}
                for s, t, r, c in src_rows
            ],
        }
    except Exception:
        logger.warning("채팅 통계 overview 집계 실패", exc_info=True)
        return dict(_OVERVIEW_EMPTY)


async def by_model(range_key: str = "all", project_id: str | None = None) -> list[dict]:
    """모델별 집계(토큰 desc). 모든 source 합산."""
    factory = _factory()
    if factory is None:
        return []
    conds = _base_conds(range_key, project_id)
    try:
        async with factory() as session:
            total_tok = ChatUsageLog.prompt_tokens + ChatUsageLog.completion_tokens
            rows = (
                await session.execute(
                    select(
                        ChatUsageLog.model_name,
                        func.coalesce(func.sum(ChatUsageLog.prompt_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.completion_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.credited_cost), 0),
                        func.coalesce(func.sum(ChatUsageLog.raw_cost), 0),
                        func.count(ChatUsageLog.id),
                    )
                    .where(*conds)
                    .group_by(ChatUsageLog.model_name)
                    .order_by(func.sum(total_tok).desc())
                )
            ).all()
        return [
            {
                "model_name": name,
                "prompt_tokens": int(pt or 0),
                "completion_tokens": int(ct or 0),
                "total_tokens": int(pt or 0) + int(ct or 0),
                "credited_cost": float(credited or 0),
                "raw_cost": float(raw or 0),
                "request_count": int(req or 0),
            }
            for name, pt, ct, credited, raw, req in rows
        ]
    except Exception:
        logger.warning("채팅 통계 by_model 집계 실패", exc_info=True)
        return []


async def by_user(
    range_key: str = "all", project_id: str | None = None, limit: int = 20, offset: int = 0
) -> list[dict]:
    """사용자별 집계(토큰 desc). source="system"(시스템 부담)은 제외 — 사용자 실사용만."""
    factory = _factory()
    if factory is None:
        return []
    conds = [*_base_conds(range_key, project_id), ChatUsageLog.source != "system"]
    try:
        async with factory() as session:
            total_tok = ChatUsageLog.prompt_tokens + ChatUsageLog.completion_tokens
            rows = (
                await session.execute(
                    select(
                        ChatUsageLog.user_id,
                        ChatUsageLog.project_id,
                        func.coalesce(func.sum(ChatUsageLog.prompt_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.completion_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.credited_cost), 0),
                        func.coalesce(func.sum(ChatUsageLog.raw_cost), 0),
                        func.count(ChatUsageLog.id),
                    )
                    .where(*conds)
                    .group_by(ChatUsageLog.user_id, ChatUsageLog.project_id)
                    .order_by(func.sum(total_tok).desc())
                    .limit(min(max(limit, 1), 200))
                    .offset(max(offset, 0))
                )
            ).all()
        return [
            {
                "user_id": uid,
                "project_id": pid,
                "prompt_tokens": int(pt or 0),
                "completion_tokens": int(ct or 0),
                "total_tokens": int(pt or 0) + int(ct or 0),
                "credited_cost": float(credited or 0),
                "raw_cost": float(raw or 0),
                "request_count": int(req or 0),
            }
            for uid, pid, pt, ct, credited, raw, req in rows
        ]
    except Exception:
        logger.warning("채팅 통계 by_user 집계 실패", exc_info=True)
        return []


def _month_ts(ym: str) -> int:
    """'YYYY-MM' → 해당 월초(UTC) epoch seconds. 파싱 실패 시 0."""
    try:
        year, month = ym.split("-")
        return int(datetime(int(year), int(month), 1, tzinfo=UTC).timestamp())
    except (ValueError, AttributeError):
        return 0


async def monthly(range_key: str = "all", project_id: str | None = None) -> list[dict]:
    """월별 시계열(오름차순). ts(월초 epoch) 포함 — TimeSeriesChart data 호환. 모든 source 합산."""
    factory = _factory()
    if factory is None:
        return []
    conds = _base_conds(range_key, project_id)
    try:
        async with factory() as session:
            month_expr = func.date_format(ChatUsageLog.created_at, "%Y-%m")
            rows = (
                await session.execute(
                    select(
                        month_expr,
                        func.coalesce(func.sum(ChatUsageLog.prompt_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.completion_tokens), 0),
                        func.coalesce(func.sum(ChatUsageLog.credited_cost), 0),
                        func.coalesce(func.sum(ChatUsageLog.raw_cost), 0),
                        func.count(ChatUsageLog.id),
                    )
                    .where(*conds)
                    .group_by(month_expr)
                    .order_by(month_expr.asc())
                )
            ).all()
        return [
            {
                "month": ym,
                "ts": _month_ts(ym),
                "prompt_tokens": int(pt or 0),
                "completion_tokens": int(ct or 0),
                "total_tokens": int(pt or 0) + int(ct or 0),
                "credited_cost": float(credited or 0),
                "raw_cost": float(raw or 0),
                "request_count": int(req or 0),
            }
            for ym, pt, ct, credited, raw, req in rows
        ]
    except Exception:
        logger.warning("채팅 통계 monthly 집계 실패", exc_info=True)
        return []


async def projects_with_usage(range_key: str = "all") -> list[str]:
    """usage_logs 에 데이터가 있는 project_id 목록(드롭다운 소스)."""
    factory = _factory()
    if factory is None:
        return []
    conds = _base_conds(range_key, None)
    try:
        async with factory() as session:
            rows = (
                await session.execute(select(ChatUsageLog.project_id).where(*conds).group_by(ChatUsageLog.project_id))
            ).all()
        return [r[0] for r in rows if r[0]]
    except Exception:
        logger.warning("채팅 통계 projects_with_usage 조회 실패", exc_info=True)
        return []
