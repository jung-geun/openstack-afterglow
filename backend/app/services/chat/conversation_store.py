"""빌트인 AI 채팅 대화/메시지 저장소 (MySQL chat_conversations / chat_messages).

⚠️ IDOR 방어: 모든 조회/수정 경로에서 대화의 user_id 가 호출자 token_info 의 user_id 와
일치하는지 검증한다(프로젝트 무관 — 한 사용자의 대화는 프로젝트가 달라도 본인 것).
타 사용자 대화 접근은 ConversationForbidden(403), 미존재는 ConversationNotFound(404).
project_id 는 생성 시점 활성 프로젝트를 메타로 보존할 뿐 소유권 판정에는 쓰지 않는다.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatConversation, ChatMessage
from app.services.k3s_crypto import decrypt_chat_content, encrypt_chat_content

logger = logging.getLogger(__name__)


def _enc(value: str | None) -> str | None:
    """평문 → chat_content 암호문. None/빈 문자열은 그대로."""
    return encrypt_chat_content(value) if value else value


def _dec(value: str | None) -> str | None:
    """암호문 → 평문(prefix 없으면 평문 passthrough). None 안전."""
    return decrypt_chat_content(value) if value else value


def _enc_json(value: list | dict | None) -> str | None:
    """tool_calls(JSON 직렬화) → 암호문. None 은 그대로."""
    if value is None:
        return None
    return encrypt_chat_content(json.dumps(value, ensure_ascii=False))


def _dec_json(value: str | None) -> list | dict | None:
    """암호문 → JSON 파싱. None/파싱 실패는 None."""
    if not value:
        return None
    try:
        return json.loads(decrypt_chat_content(value))
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("tool_calls 복호화/파싱 실패")
        return None


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
        "title": _dec(row.title),
        "model_name": row.model_name,
        "workspace_id": row.workspace_id,
        "active_leaf_id": row.active_leaf_id,
        "parent_conversation_id": row.parent_conversation_id,
        "forked_from_message_id": row.forked_from_message_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _msg_public(row: ChatMessage) -> dict:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "role": row.role,
        "parent_id": row.parent_id,
        "content": _dec(row.content),
        "tool_calls": _dec_json(row.tool_calls),
        "token_prompt": row.token_prompt,
        "token_completion": row.token_completion,
        "model_name": row.model_name,
        "created_at": _iso(row.created_at),
    }


async def _load_owned(session, conv_id: str, user_id: str) -> ChatConversation:
    """대화를 로드하고 소유권(user_id)을 검증. 프로젝트 무관 — 사용자 소유 기준.

    미존재→NotFound, 소유자(user_id) 불일치→Forbidden. project_id 는 소유권 판정에서 제외한다
    (한 사용자의 대화는 프로젝트가 달라도 본인 것). project_id 는 생성 시점 메타로만 보존된다.
    """
    row = await session.get(ChatConversation, conv_id)
    if row is None:
        raise ConversationNotFound(f"대화 {conv_id} 를 찾을 수 없습니다")
    if row.user_id != user_id:
        raise ConversationForbidden("대화에 접근할 권한이 없습니다")
    return row


async def create_conversation(
    *, project_id: str, user_id: str, title: str | None, model_name: str | None, workspace_id: int | None = None
) -> dict:
    factory = _require_db()
    row = ChatConversation(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=user_id,
        title=_enc(title or None),
        model_name=(model_name or None),
        workspace_id=workspace_id,
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _conv_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_conversations(*, user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """사용자 소유 대화 목록(프로젝트 무관). updated_at desc."""
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = (
                select(ChatConversation)
                .where(ChatConversation.user_id == user_id)
                .order_by(ChatConversation.updated_at.desc())
                .limit(min(limit, 200))
                .offset(max(offset, 0))
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [_conv_public(r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def get_conversation(conv_id: str, *, user_id: str) -> dict:
    factory = _require_db()
    try:
        async with factory() as session:
            row = await _load_owned(session, conv_id, user_id)
            return _conv_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_conversation(conv_id: str, *, user_id: str) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, conv_id, user_id)
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_title(conv_id: str, *, user_id: str, title: str | None) -> dict:
    """대화 제목 갱신(소유권 검증 + 암호화 저장). 제목 자동 요약 경로용."""
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, conv_id, user_id)
            row.title = _enc(title or None)
            await session.flush()
            return _conv_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def set_workspace(conv_id: str, *, user_id: str, workspace_id: int | None) -> dict:
    """대화를 프로젝트(workspace)에 배정/해제(소유권 검증). workspace 소유 검증은 완료 경로가 별도 수행."""
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_owned(session, conv_id, user_id)
            row.workspace_id = workspace_id
            await session.flush()
            return _conv_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_messages(conv_id: str, *, user_id: str, limit: int = 200, offset: int = 0) -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            await _load_owned(session, conv_id, user_id)  # 소유권 검증
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
    parent_id: int | None = None,
    model_name: str | None = None,
    set_leaf: bool = False,
) -> dict:
    """메시지 추가(소유권은 호출부가 이미 검증했다고 가정 — 완료 경로 내부용).

    버전 트리: parent_id 로 부모를 잇는다(같은 parent = 재생성 형제). set_leaf=True 면 대화의
    active_leaf_id 를 이 메시지로 갱신한다(활성 경로의 새 리프). model_name 은 형제 버전 라벨.
    """
    factory = _require_db()
    row = ChatMessage(
        conversation_id=conv_id,
        role=role,
        parent_id=parent_id,
        content=_enc(content),
        tool_calls=_enc_json(tool_calls),
        token_prompt=int(token_prompt),
        token_completion=int(token_completion),
        model_name=model_name,
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            if set_leaf:
                conv = await session.get(ChatConversation, conv_id)
                if conv is not None:
                    conv.active_leaf_id = row.id
            return _msg_public(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


def _backtrack(rows: list[ChatMessage], leaf_id: int | None) -> list[ChatMessage]:
    """leaf_id 에서 parent_id 를 역추적한 선형 경로(루트→리프 오름차순). leaf 없으면 빈 경로."""
    by_id = {r.id: r for r in rows}
    path: list[ChatMessage] = []
    cur = by_id.get(leaf_id) if leaf_id else None
    seen: set[int] = set()
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        path.append(cur)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    path.reverse()
    return path


async def get_active_path(conv_id: str, *, user_id: str) -> dict:
    """active_leaf 에서 역추적한 활성 경로(모델 입력·재개용). {"messages":[오름차순], "active_leaf_id"}."""
    factory = _require_db()
    try:
        async with factory() as session:
            conv = await _load_owned(session, conv_id, user_id)
            rows = (
                (await session.execute(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)))
                .scalars()
                .all()
            )
            path = _backtrack(list(rows), conv.active_leaf_id)
            return {"messages": [_msg_public(r) for r in path], "active_leaf_id": conv.active_leaf_id}
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def path_ending_at(conv_id: str, *, user_id: str, message_id: int) -> list[dict]:
    """message_id 를 리프로 한 경로(루트→message_id 오름차순). 재생성 모델 입력용."""
    factory = _require_db()
    try:
        async with factory() as session:
            await _load_owned(session, conv_id, user_id)
            rows = (
                (await session.execute(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)))
                .scalars()
                .all()
            )
            return [_msg_public(r) for r in _backtrack(list(rows), message_id)]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_message_tree(conv_id: str, *, user_id: str) -> dict:
    """전체 메시지(트리, parent_id 포함) + active_leaf_id. 프론트가 활성 경로·형제 수를 계산."""
    factory = _require_db()
    try:
        async with factory() as session:
            conv = await _load_owned(session, conv_id, user_id)
            rows = (
                (
                    await session.execute(
                        select(ChatMessage).where(ChatMessage.conversation_id == conv_id).order_by(ChatMessage.id.asc())
                    )
                )
                .scalars()
                .all()
            )
            return {"messages": [_msg_public(r) for r in rows], "active_leaf_id": conv.active_leaf_id}
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def set_active_leaf(conv_id: str, *, user_id: str, message_id: int) -> dict:
    """활성 리프를 지정 메시지로 이동(형제 버전 전환). 메시지가 이 대화 소속이어야 함."""
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            conv = await _load_owned(session, conv_id, user_id)
            msg = await session.get(ChatMessage, message_id)
            if msg is None or msg.conversation_id != conv_id:
                raise ConversationNotFound(f"메시지 {message_id} 를 대화에서 찾을 수 없습니다")
            conv.active_leaf_id = message_id
            return _conv_public(conv)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def get_message_owned(conv_id: str, *, user_id: str, message_id: int) -> ChatMessage:
    """소유권 검증 후 대화 소속 메시지 raw row 반환(재생성 parent 탐색용, 내부 전용)."""
    factory = _require_db()
    try:
        async with factory() as session:
            await _load_owned(session, conv_id, user_id)
            msg = await session.get(ChatMessage, message_id)
            if msg is None or msg.conversation_id != conv_id:
                raise ConversationNotFound(f"메시지 {message_id} 를 대화에서 찾을 수 없습니다")
            return msg
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def find_turn_start_user(conv_id: str, *, user_id: str, message_id: int) -> dict | None:
    """message_id 에서 위로 걸어 가장 가까운 role='user' 메시지(재생성 분기점). 없으면 None."""
    factory = _require_db()
    try:
        async with factory() as session:
            await _load_owned(session, conv_id, user_id)
            rows = (
                (await session.execute(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)))
                .scalars()
                .all()
            )
            by_id = {r.id: r for r in rows}
            cur = by_id.get(message_id)
            seen: set[int] = set()
            while cur is not None and cur.id not in seen:
                if cur.role == "user":
                    return _msg_public(cur)
                seen.add(cur.id)
                cur = by_id.get(cur.parent_id) if cur.parent_id else None
            return None
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def fork_conversation(conv_id: str, *, user_id: str, message_id: int) -> dict:
    """message_id 까지의 경로를 새 대화로 복사(분기). 소유자 동일, 원본 독립."""
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            conv = await _load_owned(session, conv_id, user_id)
            rows = list(
                (await session.execute(select(ChatMessage).where(ChatMessage.conversation_id == conv_id)))
                .scalars()
                .all()
            )
            by_id = {r.id: r for r in rows}
            if message_id not in by_id:
                raise ConversationNotFound(f"메시지 {message_id} 를 대화에서 찾을 수 없습니다")
            path = _backtrack(rows, message_id)  # message_id 를 리프로 간주해 역추적

            new_conv = ChatConversation(
                id=str(uuid.uuid4()),
                project_id=conv.project_id,
                user_id=user_id,
                title=conv.title,  # 암호문 그대로 복사
                model_name=conv.model_name,
                parent_conversation_id=conv_id,
                forked_from_message_id=message_id,
            )
            session.add(new_conv)
            await session.flush()

            id_map: dict[int, int] = {}  # old id -> new id (parent 재구성)
            new_leaf_id = None
            for r in path:
                new_parent = id_map.get(r.parent_id) if r.parent_id else None
                nr = ChatMessage(
                    conversation_id=new_conv.id,
                    role=r.role,
                    parent_id=new_parent,
                    content=r.content,  # 암호문 그대로 복사(재암호화 불필요)
                    tool_calls=r.tool_calls,
                    token_prompt=r.token_prompt,
                    token_completion=r.token_completion,
                    model_name=r.model_name,
                )
                session.add(nr)
                await session.flush()
                id_map[r.id] = nr.id
                new_leaf_id = nr.id
            new_conv.active_leaf_id = new_leaf_id
            return _conv_public(new_conv)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
