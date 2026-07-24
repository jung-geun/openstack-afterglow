"""Encrypted MySQL memory source of truth and semantic-index mutation outbox.

Memory namespaces are enforced before plaintext hydration.  Account memories are
the only scope shared across OpenStack projects; project and workspace memories
are never returned outside their owning project.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatMemory
from app.models.chat_jobs import ChatMemoryOutbox
from app.services.k3s_crypto import decrypt_chat_content, derive_encryption_subkey, encrypt_chat_content

logger = logging.getLogger(__name__)

_MAX_INJECT = 30  # 컨텍스트 주입 시 메모리 개수 상한(비용 방어)
_SCOPES = frozenset({"account", "project", "workspace"})


_FINGERPRINT_DOMAIN = b"chat_memory_content_fingerprint"


def memory_content_fingerprint(plaintext: str) -> str:
    """Keyed version marker; a vector database must not receive a dictionary-checkable digest."""
    return hmac.new(
        derive_encryption_subkey(_FINGERPRINT_DOMAIN),
        plaintext.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


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
        "project_id": row.project_id,
        "workspace_id": row.workspace_id,
        "scope": row.scope,
        "content": decrypt_chat_content(row.content) if row.content else None,
        "confidence": str(row.confidence) if row.confidence is not None else None,
        "expires_at": _iso(row.expires_at),
        "status": row.status,
        "is_active": row.is_active,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _validate_namespace(*, scope: str, project_id: str | None, workspace_id: int | None) -> None:
    if scope not in _SCOPES:
        raise MemoryValidationError("지원하지 않는 메모리 scope 입니다")
    if scope == "account" and project_id is None and workspace_id is None:
        return
    if scope == "project" and project_id and workspace_id is None:
        return
    if scope == "workspace" and project_id and isinstance(workspace_id, int) and workspace_id > 0:
        return
    raise MemoryValidationError("메모리 scope namespace 가 올바르지 않습니다")


def _visible_in_project(row: ChatMemory, project_id: str | None) -> bool:
    return row.scope == "account" or (project_id is not None and row.project_id == project_id)


def _scope_predicate(*, project_id: str | None, workspace_id: int | None):
    predicates = [(ChatMemory.scope == "account") & ChatMemory.project_id.is_(None) & ChatMemory.workspace_id.is_(None)]
    if project_id is not None:
        predicates.append(
            (ChatMemory.scope == "project") & (ChatMemory.project_id == project_id) & ChatMemory.workspace_id.is_(None)
        )
        if workspace_id is not None:
            predicates.append(
                (ChatMemory.scope == "workspace")
                & (ChatMemory.project_id == project_id)
                & (ChatMemory.workspace_id == workspace_id)
            )
    return or_(*predicates)


def _exact_scope_predicate(*, scope: str, project_id: str | None, workspace_id: int | None):
    _validate_namespace(scope=scope, project_id=project_id, workspace_id=workspace_id)
    return (
        (ChatMemory.scope == scope)
        & (ChatMemory.project_id.is_(None) if project_id is None else ChatMemory.project_id == project_id)
        & (ChatMemory.workspace_id.is_(None) if workspace_id is None else ChatMemory.workspace_id == workspace_id)
    )


def _not_expired_predicate():
    return or_(ChatMemory.expires_at.is_(None), ChatMemory.expires_at > datetime.now(UTC))


async def _load_owned(session, memory_id: int, user_id: str, project_id: str | None) -> ChatMemory:
    row = await session.get(ChatMemory, memory_id)
    if row is None:
        raise MemoryNotFound(f"메모리 {memory_id} 를 찾을 수 없습니다")
    if row.user_id != user_id or not _visible_in_project(row, project_id):
        raise MemoryForbidden("메모리에 접근할 권한이 없습니다")
    return row


async def _queue_semantic_mutation(session, *, row: ChatMemory, mutation: str, plaintext: str) -> None:
    """Always preserve the source mutation; freeze generations when the index is ready."""
    from app.services.chat.semantic_memory import configured_memory_index, semantic_memory_available

    required_generations: list[int] = []
    status = "pending_generation"
    if semantic_memory_available():
        try:
            required_generations = await configured_memory_index().required_generations()
            status = "queued"
        except Exception:
            logger.warning("semantic memory generation snapshot deferred", exc_info=True)
    digest = memory_content_fingerprint(plaintext)
    session.add(
        ChatMemoryOutbox(
            event_key=f"memory:{row.id}:{mutation}:{digest}:{uuid.uuid4()}",
            memory_id=row.id,
            mutation=mutation,
            content_hash=digest,
            required_generations=required_generations,
            applied_generations=[],
            status=status,
        )
    )


async def create_memory(
    *,
    user_id: str,
    content: str,
    scope: str = "account",
    project_id: str | None = None,
    workspace_id: int | None = None,
) -> dict:
    if not content or not content.strip():
        raise MemoryValidationError("content 는 필수입니다")
    _validate_namespace(scope=scope, project_id=project_id, workspace_id=workspace_id)
    factory = _require_db()
    row = ChatMemory(
        user_id=user_id,
        project_id=project_id,
        workspace_id=workspace_id,
        scope=scope,
        content=encrypt_chat_content(content.strip()),
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            await _queue_semantic_mutation(session, row=row, mutation="upsert", plaintext=content.strip())
            return _public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_memories(*, user_id: str, project_id: str | None = None, workspace_id: int | None = None) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ChatMemory)
                        .where(
                            ChatMemory.user_id == user_id,
                            ChatMemory.status == "active",
                            _not_expired_predicate(),
                            _scope_predicate(project_id=project_id, workspace_id=workspace_id),
                        )
                        .order_by(ChatMemory.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            return [_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def hydrate_candidate_ids(
    *,
    ids: list[int],
    user_id: str,
    scope: str,
    project_id: str | None,
    workspace_id: int | None,
) -> list[dict]:
    """Rehydrate vector candidates only after repeating exact MySQL namespace checks."""
    if not ids:
        return []
    predicate = _exact_scope_predicate(scope=scope, project_id=project_id, workspace_id=workspace_id)
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ChatMemory).where(
                            ChatMemory.id.in_(set(ids)),
                            ChatMemory.user_id == user_id,
                            ChatMemory.status == "active",
                            ChatMemory.is_active.is_(True),
                            _not_expired_predicate(),
                            predicate,
                        )
                    )
                )
                .scalars()
                .all()
            )
            by_id = {row.id: _public(row) for row in rows}
            return [by_id[memory_id] for memory_id in ids if memory_id in by_id]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_memory(memory_id: int, *, user_id: str, project_id: str | None = None, patch: dict) -> dict:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, memory_id, user_id, project_id)
            if "content" in patch:
                c = (patch["content"] or "").strip()
                if not c:
                    raise MemoryValidationError("content 는 필수입니다")
                row.content = encrypt_chat_content(c)
                await _queue_semantic_mutation(session, row=row, mutation="upsert", plaintext=c)
            if patch.get("is_active") is not None:
                row.is_active = bool(patch["is_active"])
            return _public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_memory(memory_id: int, *, user_id: str, project_id: str | None = None) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, memory_id, user_id, project_id)
            row.status = "deleting"
            row.is_active = False
            plaintext = decrypt_chat_content(row.content) if row.content else ""
            await _queue_semantic_mutation(session, row=row, mutation="delete", plaintext=plaintext)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def active_contents_for_run(
    *,
    user_id: str,
    project_id: str | None,
    workspace_id: int | None = None,
) -> list[str]:
    """Hydrate only active MySQL rows in the caller's exact visible namespaces."""
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
                        .where(
                            ChatMemory.user_id == user_id,
                            ChatMemory.is_active.is_(True),
                            ChatMemory.status == "active",
                            _not_expired_predicate(),
                            _scope_predicate(project_id=project_id, workspace_id=workspace_id),
                        )
                        .order_by(ChatMemory.updated_at.desc())
                        .limit(_MAX_INJECT)
                    )
                )
                .scalars()
                .all()
            )
            return [
                plaintext for row in rows if (plaintext := decrypt_chat_content(row.content) if row.content else None)
            ]
    except Exception:
        logger.warning("메모리 주입 조회 실패", exc_info=True)
        return []
