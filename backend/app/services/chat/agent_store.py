"""빌트인 AI 채팅 에이전트 저장소 — 프롬프트+모델+파라미터+MCP/툴 묶음 (MySQL chat_agents).

⚠️ 소유권(IDOR): 조회는 소유자 본인 또는 visibility='public'만 허용, 수정/삭제는 소유자만.
instructions 는 AES-256-GCM(chat_content 도메인) 암호문으로 저장하고 조회 시 복호화한다.
허브 복제(clone)는 공개(또는 본인) 에이전트를 본인 소유의 private 사본으로 복사한다.
"""

from __future__ import annotations

import logging

from sqlalchemy import or_, select, update
from sqlalchemy.exc import OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatAgent
from app.services.k3s_crypto import decrypt_chat_content, encrypt_chat_content

logger = logging.getLogger(__name__)

_VISIBILITIES = ("private", "public")


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — fail-closed(503)."""


class AgentNotFound(LookupError):
    """에이전트 미존재 — 404."""


class AgentForbidden(PermissionError):
    """소유자 불일치(비공개 타인 접근/수정) — 403."""


class AgentValidationError(ValueError):
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


def _dec(v: str | None) -> str | None:
    return decrypt_chat_content(v) if v else v


def _enc(v: str | None) -> str | None:
    return encrypt_chat_content(v) if v else v


def _public(row: ChatAgent, *, owner_view: bool = False) -> dict:
    """에이전트 공개 dict. 공개 에이전트는 instructions 를 공유(허브 복제 대상)한다."""
    return {
        "id": row.id,
        "owner_user_id": row.owner_user_id,
        "name": row.name,
        "description": row.description,
        "avatar": row.avatar,
        "instructions": _dec(row.instructions),
        "model_name": row.model_name,
        "params": row.params or {},
        "mcp_ids": row.mcp_ids or [],
        "tool_ids": row.tool_ids or [],
        "visibility": row.visibility,
        "cloned_from_id": row.cloned_from_id,
        "clone_count": row.clone_count,
        "is_owner": owner_view,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _validate(name: str | None, visibility: str | None) -> None:
    if name is not None and not name.strip():
        raise AgentValidationError("name 은 필수입니다")
    if visibility is not None and visibility not in _VISIBILITIES:
        raise AgentValidationError("visibility 는 private|public 이어야 합니다")


async def create_agent(
    *,
    owner_user_id: str,
    name: str,
    description: str | None = None,
    avatar: str | None = None,
    instructions: str | None = None,
    model_name: str | None = None,
    params: dict | None = None,
    mcp_ids: list | None = None,
    tool_ids: list | None = None,
    visibility: str = "private",
) -> dict:
    factory = _require_db()
    _validate(name, visibility)
    row = ChatAgent(
        owner_user_id=owner_user_id,
        name=name.strip(),
        description=(description or None),
        avatar=(avatar or None),
        instructions=_enc(instructions or None),
        model_name=(model_name or None),
        params=(params or None),
        mcp_ids=(mcp_ids or None),
        tool_ids=(tool_ids or None),
        visibility=visibility,
    )
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _public(row, owner_view=True)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_agents(*, user_id: str) -> list[dict]:
    """본인 소유 에이전트 목록(updated_at desc)."""
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ChatAgent)
                        .where(ChatAgent.owner_user_id == user_id)
                        .order_by(ChatAgent.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            return [_public(r, owner_view=True) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_public(*, query: str = "", limit: int = 30, offset: int = 0, user_id: str = "") -> list[dict]:
    """허브 — 공개 에이전트 검색(이름·설명), clone_count desc. is_owner 로 본인 것 표시."""
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = select(ChatAgent).where(ChatAgent.visibility == "public")
            q = (query or "").strip()
            if q:
                like = f"%{q}%"
                stmt = stmt.where(or_(ChatAgent.name.like(like), ChatAgent.description.like(like)))
            stmt = stmt.order_by(ChatAgent.clone_count.desc(), ChatAgent.id.desc())
            stmt = stmt.limit(min(max(limit, 1), 100)).offset(max(offset, 0))
            rows = (await session.execute(stmt)).scalars().all()
            return [_public(r, owner_view=(r.owner_user_id == user_id)) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def _load(session, agent_id: int) -> ChatAgent:
    row = await session.get(ChatAgent, agent_id)
    if row is None:
        raise AgentNotFound(f"에이전트 {agent_id} 를 찾을 수 없습니다")
    return row


async def get_agent(agent_id: int, *, user_id: str) -> dict:
    """소유자 본인 또는 공개 에이전트만 조회 가능. 비공개 타인 접근은 Forbidden."""
    factory = _require_db()
    try:
        async with factory() as session:
            row = await _load(session, agent_id)
            if row.owner_user_id != user_id and row.visibility != "public":
                raise AgentForbidden("에이전트에 접근할 권한이 없습니다")
            return _public(row, owner_view=(row.owner_user_id == user_id))
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def update_agent(agent_id: int, *, user_id: str, patch: dict) -> dict:
    """소유자만 수정. instructions 는 재암호화 저장."""
    factory = _require_db()
    _validate(patch.get("name"), patch.get("visibility"))
    try:
        async with factory() as session, session.begin():
            row = await _load(session, agent_id)
            if row.owner_user_id != user_id:
                raise AgentForbidden("에이전트를 수정할 권한이 없습니다")
            if patch.get("name"):
                row.name = str(patch["name"]).strip()
            if "description" in patch:
                row.description = patch["description"] or None
            if "avatar" in patch:
                row.avatar = patch["avatar"] or None
            if "instructions" in patch:
                row.instructions = _enc(patch["instructions"] or None)
            if "model_name" in patch:
                row.model_name = patch["model_name"] or None
            if "params" in patch:
                row.params = patch["params"] or None
            if "mcp_ids" in patch:
                row.mcp_ids = patch["mcp_ids"] or None
            if "tool_ids" in patch:
                row.tool_ids = patch["tool_ids"] or None
            if patch.get("visibility"):
                row.visibility = patch["visibility"]
            await session.flush()
            return _public(row, owner_view=True)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_agent(agent_id: int, *, user_id: str) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load(session, agent_id)
            if row.owner_user_id != user_id:
                raise AgentForbidden("에이전트를 삭제할 권한이 없습니다")
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def clone_agent(agent_id: int, *, user_id: str) -> dict:
    """공개(또는 본인) 에이전트를 본인 소유 private 사본으로 복제. 출처 clone_count 증가.

    ⚠️ mcp_ids/tool_ids 는 그대로 복사하되, 복제자가 접근 불가한 비공개 확장이면 실행 시 무시된다
    (tool_runtime 이 소유권을 재검증). 여기서는 참조만 복사한다.
    """
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            src = await _load(session, agent_id)
            if src.owner_user_id != user_id and src.visibility != "public":
                raise AgentForbidden("복제할 권한이 없습니다")
            clone = ChatAgent(
                owner_user_id=user_id,
                name=src.name,
                description=src.description,
                avatar=src.avatar,
                instructions=src.instructions,  # 암호문 그대로 복사(재암호화 불필요)
                model_name=src.model_name,
                params=src.params,
                mcp_ids=src.mcp_ids,
                tool_ids=src.tool_ids,
                visibility="private",
                cloned_from_id=src.id,
            )
            session.add(clone)
            # 출처 인기 지표 증가(본인 복제는 제외)
            if src.owner_user_id != user_id:
                await session.execute(
                    update(ChatAgent).where(ChatAgent.id == src.id).values(clone_count=ChatAgent.clone_count + 1)
                )
            await session.flush()
            return _public(clone, owner_view=True)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def get_agent_for_run(agent_id: int, *, user_id: str) -> dict | None:
    """완료 경로용 — 소유자 본인 또는 공개 에이전트의 실행 설정. 미접근/미존재 시 None.

    ⚠️ 반환 instructions 는 복호화 평문 — 시스템 프롬프트 주입 전용, 응답 노출 금지.
    """
    factory = _require_db()
    try:
        async with factory() as session:
            row = await session.get(ChatAgent, agent_id)
            if row is None:
                return None
            if row.owner_user_id != user_id and row.visibility != "public":
                return None
            return {
                "id": row.id,
                "instructions": _dec(row.instructions),
                "model_name": row.model_name,
                "params": row.params or {},
                "mcp_ids": row.mcp_ids or [],
                "tool_ids": row.tool_ids or [],
            }
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
