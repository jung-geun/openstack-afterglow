"""사용자 활동 로그 기록 / 조회 서비스. Best-effort: 기록 실패는 logger.warning 만."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Literal

from sqlalchemy import and_, desc, select

from app.database import get_session_factory, is_db_available
from app.models.activity import ActivityLog

logger = logging.getLogger(__name__)

ActionStatus = Literal["started", "success", "failed"]

# 자동 로깅 미들웨어와의 중복 억제 채널.
# BaseHTTPMiddleware 는 엔드포인트를 자식 태스크(컨텍스트 복사본)에서 실행하므로
# ContextVar 바인딩 변경은 미들웨어로 전달되지 않는다. 하지만 값(dict 참조)은
# 복사 시 참조로 공유되므로, dict 내용 변경은 양쪽에서 보인다.
# 미들웨어가 dict 를 set 하고 핸들러가 record() 를 호출하면 dict["logged"]=True 가
# 미들웨어 쪽에도 반영되어 자동 로깅을 억제한다.
_audit_ctx: ContextVar[dict | None] = ContextVar("activity_audit", default=None)

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
    # 자동 로깅 미들웨어에 "명시적 로그가 발생했음"을 신호 (중복 방지).
    # rec() 경유 호출 + k3s 서비스의 직접 record() 2곳 모두 여기서 신호를 세팅한다.
    _h = _audit_ctx.get()
    if _h is not None:
        _h["logged"] = True
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


async def get_user_activity_bounds(user_ids: list[str]) -> dict[str, dict]:
    """사용자별 최초·최근 활동 시각을 1쿼리로 배치 조회.

    Returns:
        {user_id: {"first_seen": isoformat | None, "last_seen": isoformat | None}}
        활동 기록 없는 user_id는 결과에 포함되지 않는다.
    """
    if not user_ids or not is_db_available():
        return {}
    factory = get_session_factory()
    if factory is None:
        return {}
    from sqlalchemy import func

    async with factory() as session:
        stmt = (
            select(
                ActivityLog.user_id,
                func.min(ActivityLog.created_at).label("first_seen"),
                func.max(ActivityLog.created_at).label("last_seen"),
            )
            .where(ActivityLog.user_id.in_(user_ids))
            .group_by(ActivityLog.user_id)
        )
        rows = (await session.execute(stmt)).all()
        return {
            row.user_id: {
                "first_seen": row.first_seen.isoformat() if row.first_seen else None,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in rows
        }


async def list_user_management_events(
    *,
    limit: int = 50,
    before_id: int | None = None,
) -> list[dict]:
    """관리자용. resource_type='user' 이벤트를 cross-project로 시간 역순 조회.

    사용자 생성·수정·삭제 변경 로그 카드에 사용.
    """
    if not is_db_available():
        return []
    factory = get_session_factory()
    if factory is None:
        return []
    async with factory() as session:
        conds = [ActivityLog.resource_type == "user"]
        if before_id is not None:
            conds.append(ActivityLog.id < before_id)
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
