"""빌트인 AI 채팅 대화/메시지 저장소 (MySQL chat_conversations / chat_messages).

⚠️ IDOR 방어: 모든 조회/수정 경로에서 대화의 (project_id, user_id) 가 호출자 token_info 와
일치하는지 검증한다. 타 프로젝트 대화 접근은 ConversationForbidden(403), 미존재는 ConversationNotFound(404).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatConversation, ChatMessage

logger = logging.getLogger(__name__)


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — fail-closed(503)."""


class ConversationNotFound(LookupError):
    """대화 미존재 — 404."""


class ConversationForbidden(PermissionError):
    """대화 소유자 불일치(타 프로젝트/타 사용자) — 403."""


def _require_db():
    if not is_db_available():
        raise ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 가 구성되지 않았습니다")
    return factory


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _conv_public(row: ChatConversation) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "user_id": row.user_id,
        "title": row.title,
        "model_name": row.model_name,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _msg_public(row: ChatMessage) -> dict:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "role": row.role,
        "content": row.content,
        "tool_calls": row.tool_calls,
        "token_prompt": row.token_prompt,
        "token_completion": row.token_completion,
        "created_at": _iso(row.created_at),
    }


async def _load_owned(session, conv_id: str, project_id: str, user_id: str) -> ChatConversation:
    """대화를 로드하고 소유권을 검증. 미존재→NotFound, 소유자 불일치→Forbidden."""
    row = await session.get(ChatConversation, conv_id)
    if row is None:
        raise ConversationNotFound(f"대화 {conv_id} 를 찾을 수 없습니다")
    if row.project_id != project_id or row.user_id != user_id:
        raise ConversationForbidden("대화에 접근할 권한이 없습니다")
    return row


async def create_conversation(*, project_id: str, user_id: str, title: str | None, model_name: str | None) -> dict:
    factory = _require_db()
    row = ChatConversation(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=user_id,
        title=(title or None),
        model_name=(model_name or None),
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _conv_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_conversations(*, project_id: str, user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = (
                select(ChatConversation)
                .where(ChatConversation.project_id == project_id, ChatConversation.user_id == user_id)
                .order_by(ChatConversation.updated_at.desc())
                .limit(min(limit, 200))
                .offset(max(offset, 0))
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_conv_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def get_conversation(conv_id: str, *, project_id: str, user_id: str) -> dict:
    factory = _require_db()
    try:
        async with factory() as session:
            row = await _load_owned(session, conv_id, project_id, user_id)
            return _conv_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_conversation(conv_id: str, *, project_id: str, user_id: str) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, conv_id, project_id, user_id)
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_messages(
    conv_id: str, *, project_id: str, user_id: str, limit: int = 200, offset: int = 0
) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            await _load_owned(session, conv_id, project_id, user_id)  # 소유권 검증
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conv_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .limit(min(limit, 500))
                .offset(max(offset, 0))
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_msg_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def add_message(
    conv_id: str,
    *,
    role: str,
    content: str | None,
    tool_calls: list | None = None,
    token_prompt: int = 0,
    token_completion: int = 0,
) -> dict:
    """메시지 추가(소유권은 호출부가 이미 검증했다고 가정 — 완료 경로 내부용)."""
    factory = _require_db()
    row = ChatMessage(
        conversation_id=conv_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        token_prompt=int(token_prompt),
        token_completion=int(token_completion),
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _msg_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
