"""사용자 활동 로그 기록 / 조회 서비스. Best-effort: 기록 실패는 logger.warning 만."""

from __future__ import annotations

import logging
import time
from typing import Literal

from sqlalchemy import and_, desc, select

from app.database import get_session_factory, is_db_available
from app.models.activity import ActivityLog

logger = logging.getLogger(__name__)

ActionStatus = Literal["started", "success", "failed"]

_last_db_warn_ts: float = float("-inf")  # 첫 번째 경고는 항상 즉시 출력


def _warn_db_unavailable(msg: str) -> None:
    global _last_db_warn_ts
    now = time.monotonic()
    if now - _last_db_warn_ts >= 60.0:
        logger.warning(msg)
        _last_db_warn_ts = now


async def record(
    *,
    project_id: str,
    user_id: str,
    username: str,
    resource_type: str,
    action: str,
    status: ActionStatus,
    resource_id: str | None = None,
    resource_name: str | None = None,
    error_message: str | None = None,
    extra: dict | None = None,
) -> None:
    """활동 1건 기록. 실패 시 silently swallow + warning."""
    if not is_db_available():
        _warn_db_unavailable("ActivityLog skipped: db unavailable (engine=None or circuit breaker open)")
        return
    factory = get_session_factory()
    if factory is None:
        _warn_db_unavailable("ActivityLog skipped: session_factory is None")
        return
    try:
        async with factory() as session:
            row = ActivityLog(
                project_id=project_id,
                user_id=user_id,
                username=username,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name[:255] if resource_name else None,
                action=action,
                status=status,
                error_message=error_message[:65535] if error_message else None,
                extra=extra,
            )
            session.add(row)
            await session.commit()
    except Exception:
        logger.warning(
            "activity_log 기록 실패 (action=%s resource_type=%s)",
            action,
            resource_type,
            exc_info=True,
        )


async def list_for_project(
    project_id: str,
    *,
    limit: int = 50,
    before_id: int | None = None,
    resource_type: str | None = None,
    action: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """admin 화면용. project 안의 모든 사용자 활동을 시간 역순으로."""
    if not is_db_available():
        return []
    factory = get_session_factory()
    if factory is None:
        return []
    async with factory() as session:
        conds = [ActivityLog.project_id == project_id]
        if before_id is not None:
            conds.append(ActivityLog.id < before_id)
        if resource_type:
            conds.append(ActivityLog.resource_type == resource_type)
        if action:
            conds.append(ActivityLog.action == action)
        if user_id:
            conds.append(ActivityLog.user_id == user_id)
        stmt = select(ActivityLog).where(and_(*conds)).order_by(desc(ActivityLog.id)).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_dict(r) for r in rows]


async def list_for_user(
    user_id: str,
    *,
    limit: int = 50,
    before_id: int | None = None,
    resource_type: str | None = None,
    action: str | None = None,
) -> list[dict]:
    """account 페이지용. 본인 활동만 (cross-project)."""
    if not is_db_available():
        return []
    factory = get_session_factory()
    if factory is None:
        return []
    async with factory() as session:
        conds = [ActivityLog.user_id == user_id]
        if before_id is not None:
            conds.append(ActivityLog.id < before_id)
        if resource_type:
            conds.append(ActivityLog.resource_type == resource_type)
        if action:
            conds.append(ActivityLog.action == action)
        stmt = select(ActivityLog).where(and_(*conds)).order_by(desc(ActivityLog.id)).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_dict(r) for r in rows]


def _row_to_dict(r: ActivityLog) -> dict:
    return {
        "id": r.id,
        "created_at": r.created_at.isoformat(),
        "project_id": r.project_id,
        "user_id": r.user_id,
        "username": r.username,
        "resource_type": r.resource_type,
        "resource_id": r.resource_id,
        "resource_name": r.resource_name,
        "action": r.action,
        "status": r.status,
        "error_message": r.error_message,
        "extra": r.extra,
    }
