"""빌트인 AI 채팅 확장(MCP 서버 / 커스텀 HTTP 툴) 관리 저장소 (MySQL).

스코프 모델:
- scope='global' (owner_* NULL): 관리자만 생성/수정/삭제, 모든 사용자에게 적용.
- scope='user' (owner_user_id/owner_project_id): 소유자만 생성/수정/삭제, 본인에게만 적용.

⚠️ IDOR: user 스코프 수정/삭제는 (owner_user_id, owner_project_id)가 요청자와 일치할 때만 허용.
사용자는 목록에서 자신의 것 + 활성 global 만 본다.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatCustomTool, ChatMcpServer

logger = logging.getLogger(__name__)

_MODELS = {"mcp": ChatMcpServer, "tool": ChatCustomTool}


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — 503."""


class ExtensionNotFound(LookupError):
    """대상 미존재 — 404."""


class ExtensionForbidden(PermissionError):
    """소유자 불일치/스코프 위반 — 403."""


class ExtensionValidationError(ValueError):
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


def _public_mcp(row: ChatMcpServer) -> dict:
    return {
        "id": row.id,
        "scope": row.scope,
        "name": row.name,
        "transport": row.transport,
        "url": row.url,
        "command": row.command,
        "headers": row.headers,
        "is_active": row.is_active,
        "created_at": _iso(row.created_at),
    }


def _public_tool(row: ChatCustomTool) -> dict:
    return {
        "id": row.id,
        "scope": row.scope,
        "name": row.name,
        "description": row.description,
        "method": row.method,
        "url": row.url,
        "params_schema": row.params_schema,
        "timeout_seconds": row.timeout_seconds,
        "is_active": row.is_active,
        "created_at": _iso(row.created_at),
    }


_PUBLIC = {"mcp": _public_mcp, "tool": _public_tool}


def _model(kind: str):
    m = _MODELS.get(kind)
    if m is None:
        raise ExtensionValidationError(f"알 수 없는 확장 종류: {kind}")
    return m


def _apply_fields(kind: str, row, fields: dict) -> None:
    """kind 별 허용 필드만 row 에 반영(화이트리스트). 소유권/스코프 필드는 여기서 다루지 않음."""
    if kind == "mcp":
        if "name" in fields and fields["name"]:
            row.name = str(fields["name"]).strip()
        if "transport" in fields and fields["transport"]:
            if fields["transport"] not in ("http", "sse", "stdio"):
                raise ExtensionValidationError("transport 는 http|sse|stdio 중 하나여야 합니다")
            row.transport = fields["transport"]
        if "url" in fields:
            row.url = fields["url"] or None
        if "command" in fields:
            row.command = fields["command"] or None
        if "headers" in fields:
            row.headers = fields["headers"] or None
    else:  # tool
        if "name" in fields and fields["name"]:
            name = str(fields["name"]).strip()
            if not name.replace("_", "").isalnum():
                raise ExtensionValidationError("툴 이름은 영숫자/언더스코어만 허용됩니다")
            row.name = name
        if "description" in fields and fields["description"]:
            row.description = str(fields["description"]).strip()
        if "method" in fields and fields["method"]:
            if fields["method"].upper() not in ("GET", "POST"):
                raise ExtensionValidationError("method 는 GET|POST 만 허용됩니다")
            row.method = fields["method"].upper()
        if "url" in fields and fields["url"]:
            row.url = str(fields["url"]).strip()
        if "params_schema" in fields:
            row.params_schema = fields["params_schema"] or None
        if "timeout_seconds" in fields and fields["timeout_seconds"] is not None:
            row.timeout_seconds = max(1, min(int(fields["timeout_seconds"]), 60))
    if "is_active" in fields and fields["is_active"] is not None:
        row.is_active = bool(fields["is_active"])


async def list_global(kind: str) -> list[dict]:
    """관리자용 — global 스코프 전체."""
    model = _model(kind)
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (
                (await session.execute(select(model).where(model.scope == "global").order_by(model.id))).scalars().all()
            )
            return [_PUBLIC[kind](r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_for_user(kind: str, *, user_id: str, project_id: str, active_only: bool = False) -> list[dict]:
    """사용자용 — 활성 global + 본인 user 스코프."""
    model = _model(kind)
    factory = _require_db()
    try:
        async with factory() as session:
            stmt = select(model).where(
                ((model.scope == "global") & (model.is_active.is_(True)))
                | ((model.scope == "user") & (model.owner_user_id == user_id) & (model.owner_project_id == project_id))
            )
            if active_only:
                stmt = stmt.where(model.is_active.is_(True))
            rows = (await session.execute(stmt.order_by(model.id))).scalars().all()
            return [_PUBLIC[kind](r) for r in rows]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def create(
    kind: str,
    fields: dict,
    *,
    scope: str,
    owner_user_id: str | None = None,
    owner_project_id: str | None = None,
) -> dict:
    model = _model(kind)
    if scope not in ("global", "user"):
        raise ExtensionValidationError("scope 는 global|user 여야 합니다")
    if scope == "user" and (not owner_user_id or not owner_project_id):
        raise ExtensionValidationError("user 스코프는 소유자 정보가 필요합니다")
    if not fields.get("name"):
        raise ExtensionValidationError("name 은 필수입니다")
    if kind == "tool" and not fields.get("url"):
        raise ExtensionValidationError("커스텀 툴은 url 이 필수입니다")

    row = model(
        scope=scope,
        owner_user_id=(owner_user_id if scope == "user" else None),
        owner_project_id=(owner_project_id if scope == "user" else None),
        # tool 필수 컬럼 기본값(스키마 NOT NULL) — _apply_fields 가 덮어씀
        **({"description": "", "url": ""} if kind == "tool" else {}),
    )
    _apply_fields(kind, row, fields)
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            session.add(row)
            await session.flush()
            return _PUBLIC[kind](row)
    except IntegrityError as exc:
        raise ExtensionValidationError("제약 위반(중복 등)") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def _load_authorized(
    session, model, item_id: int, *, requester_user_id: str | None, requester_project_id: str | None, admin: bool
):
    row = await session.get(model, item_id)
    if row is None:
        raise ExtensionNotFound(f"{item_id} 를 찾을 수 없습니다")
    if row.scope == "global":
        if not admin:
            raise ExtensionForbidden("global 확장은 관리자만 변경할 수 있습니다")
    else:  # user
        if admin:
            pass  # 관리자는 열람/변경 허용
        elif row.owner_user_id != requester_user_id or row.owner_project_id != requester_project_id:
            raise ExtensionForbidden("소유자가 아닙니다")
    return row


async def update(
    kind: str,
    item_id: int,
    patch: dict,
    *,
    requester_user_id: str | None = None,
    requester_project_id: str | None = None,
    admin: bool = False,
) -> dict:
    model = _model(kind)
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_authorized(
                session,
                model,
                item_id,
                requester_user_id=requester_user_id,
                requester_project_id=requester_project_id,
                admin=admin,
            )
            _apply_fields(kind, row, patch)
            await session.flush()
            return _PUBLIC[kind](row)
    except IntegrityError as exc:
        raise ExtensionValidationError("제약 위반") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete(
    kind: str,
    item_id: int,
    *,
    requester_user_id: str | None = None,
    requester_project_id: str | None = None,
    admin: bool = False,
) -> None:
    model = _model(kind)
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await _load_authorized(
                session,
                model,
                item_id,
                requester_user_id=requester_user_id,
                requester_project_id=requester_project_id,
                admin=admin,
            )
            await session.delete(row)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc
