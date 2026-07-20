"""빌트인 AI 채팅 사용자 메모리 저장소 — 장기 기억 (MySQL chat_memories).

⚠️ 소유권: user_id 스코프. 프로젝트 무관(사용자 전체에 적용). content 는 chat_content 암호문.
완료 경로가 활성 메모리를 컨텍스트(system)로 주입한다. v1 은 수동 관리, 자동 추출은 후속.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatMemory
from app.services.k3s_crypto import decrypt_chat_content, encrypt_chat_content

logger = logging.getLogger(__name__)

_MAX_INJECT = 30  # 컨텍스트 주입 시 메모리 개수 상한(비용 방어)


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — fail-closed(503)."""


class MemoryNotFound(LookupError):
    """메모리 미존재 — 404."""


class MemoryForbidden(PermissionError):
    """소유자 불일치 — 403."""


class MemoryValidationError(ValueError):
    """입력 검증 실패 — 400."""


def _require_db():
    if not is_db_available():
        raise ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 가 구성되지 않았습니다")
    return factory


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _public(row: ChatMemory) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "content": decrypt_chat_content(row.content) if row.content else None,
        "is_active": row.is_active,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


async def _load_owned(session, memory_id: int, user_id: str) -> ChatMemory:
    row = await session.get(ChatMemory, memory_id)
    if row is None:
        raise MemoryNotFound(f"메모리 {memory_id} 를 찾을 수 없습니다")
    if row.user_id != user_id:
        raise MemoryForbidden("메모리에 접근할 권한이 없습니다")
    return row


async def create_memory(*, user_id: str, content: str) -> dict:
    factory = _require_db()
    if not content or not content.strip():
        raise MemoryValidationError("content 는 필수입니다")
    row = ChatMemory(user_id=user_id, content=encrypt_chat_content(content.strip()))
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_memories(*, user_id: str) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ChatMemory).where(ChatMemory.user_id == user_id).order_by(ChatMemory.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            return [_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_memory(memory_id: int, *, user_id: str, patch: dict) -> dict:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, memory_id, user_id)
            if "content" in patch:
                c = (patch["content"] or "").strip()
                if not c:
                    raise MemoryValidationError("content 는 필수입니다")
                row.content = encrypt_chat_content(c)
            if patch.get("is_active") is not None:
                row.is_active = bool(patch["is_active"])
            await session.flush()
            return _public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_memory(memory_id: int, *, user_id: str) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, memory_id, user_id)
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def active_contents_for_run(*, user_id: str) -> list[str]:
    """완료 경로용 — 활성 메모리 content 목록(복호화, 상한 적용). 실패 시 빈 목록(부가 기능)."""
    if not is_db_available():
        return []
    factory = get_session_factory()
    if factory is None:
        return []
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ChatMemory)
                        .where(ChatMemory.user_id == user_id, ChatMemory.is_active.is_(True))
                        .order_by(ChatMemory.updated_at.desc())
                        .limit(_MAX_INJECT)
                    )
                )
                .scalars()
                .all()
            )
            out = []
            for r in rows:
                c = decrypt_chat_content(r.content) if r.content else None
                if c:
                    out.append(c)
            return out
    except Exception:
        logger.warning("메모리 주입 조회 실패", exc_info=True)
        return []
