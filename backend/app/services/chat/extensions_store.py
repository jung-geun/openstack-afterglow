"""빌트인 AI 채팅 확장(MCP 서버 / 커스텀 HTTP 툴) 관리 저장소 (MySQL).

스코프 모델:
- scope='global' (owner_* NULL): 관리자만 생성/수정/삭제, 모든 사용자에게 적용.
- scope='user' (owner_user_id/owner_project_id): 소유자만 생성/수정/삭제, 본인에게만 적용.

⚠️ IDOR: user 스코프 수정/삭제는 (owner_user_id, owner_project_id)가 요청자와 일치할 때만 허용.
사용자는 목록에서 자신의 것 + 활성 global 만 본다.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.chat_db import ChatCustomTool, ChatMcpCredential, ChatMcpOAuthConnection, ChatMcpServer, ChatSkill
from app.services.k3s_crypto import (
    decrypt_chat_content,
    decrypt_llm_provider_key,
    encrypt_chat_content,
    encrypt_llm_provider_key,
)

logger = logging.getLogger(__name__)

_MODELS = {"mcp": ChatMcpServer, "tool": ChatCustomTool, "skill": ChatSkill}

# MCP supports only HTTPS streamable HTTP. Local process and legacy SSE transports are rejected.
_MCP_TRANSPORTS = ("http",)


def _is_notion_mcp_url(value: object) -> bool:
    return isinstance(value, str) and value.strip().rstrip("/").lower() == "https://mcp.notion.com/mcp"


def _mcp_auth_mode(row: ChatMcpServer) -> str:
    """Classify legacy rows safely; hosted Notion is OAuth-only regardless of stale metadata."""
    if _is_notion_mcp_url(row.url):
        return "oauth"
    mode = getattr(row, "auth_mode", None)
    if mode in {"none", "headers", "oauth"}:
        return mode
    return "headers" if _clean_requirements(row.auth_requirements) else "none"


class ChatStorageUnavailable(RuntimeError):
    """chat DB 미구성/장애 — 503."""


class ExtensionNotFound(LookupError):
    """대상 미존재 — 404."""


class ExtensionForbidden(PermissionError):
    """소유자 불일치/스코프 위반 — 403."""


class ExtensionValidationError(ValueError):
    """입력 검증 실패 — 400."""


class ExtensionSecretUnavailable(RuntimeError):
    """An encrypted extension secret cannot be safely used."""


def _require_db():
    if not is_db_available():
        raise ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 가 구성되지 않았습니다")
    return factory


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _decrypt_headers(row: ChatMcpServer, *, fail_closed: bool = False) -> dict:
    """Restore MCP headers, refusing execution when an encrypted value is invalid."""
    if row.encrypted_headers:
        try:
            data = json.loads(decrypt_llm_provider_key(row.encrypted_headers))
            if not isinstance(data, dict):
                raise ValueError("decrypted MCP headers are not an object")
            return data
        except Exception as exc:
            logger.warning("MCP 헤더 복호 실패 id=%s", row.id, exc_info=True)
            if fail_closed:
                raise ExtensionSecretUnavailable("MCP 인증 헤더를 복호화할 수 없습니다") from exc
            return {}
    if isinstance(row.headers, dict):  # 레거시 plaintext
        return row.headers
    return {}


def _mask_headers(headers: dict) -> dict:
    """헤더 값은 시크릿(Authorization 토큰 등)일 수 있으므로 키만 노출하고 값은 가린다."""
    return {k: "••••••" for k in headers}


def _public_mcp(row: ChatMcpServer) -> dict:
    # The API reveals header names (never values) so clients can retain masked fields.
    # A corrupt ciphertext yields no names but remains marked as configured; execution fails closed.
    headers = _decrypt_headers(row)
    return {
        "id": row.id,
        "scope": row.scope,
        "name": row.name,
        "transport": row.transport,
        "url": row.url,
        "headers": _mask_headers(headers),
        "has_headers": bool(row.encrypted_headers) or bool(headers),
        # 사용자별 인증 요구사항(비밀 아님) — 프론트가 어떤 값을 사용자에게 요구할지 표시.
        "auth_mode": _mcp_auth_mode(row),
        "auth_requirements": _clean_requirements(row.auth_requirements),
        "is_active": row.is_active,
        "effect_overrides": row.tool_effect_overrides,
        "config_version": row.config_version,
        "created_at": _iso(row.created_at),
    }


def _reveal_mcp(row: ChatMcpServer) -> dict:
    """실행 경로(tool_runtime→mcp_client) 전용 — 복호화된 실제 헤더를 포함. API 응답에 쓰지 말 것."""
    return {
        "id": row.id,
        "name": row.name,
        "transport": row.transport,
        "url": row.url,
        "headers": _decrypt_headers(row, fail_closed=True),
        "auth_requirements": _clean_requirements(row.auth_requirements),
        "auth_mode": _mcp_auth_mode(row),
        "is_active": row.is_active,
        "effect_overrides": row.tool_effect_overrides,
        "config_version": row.config_version,
    }


def _clean_requirements(raw) -> list[dict]:
    """auth_requirements 정규화 — [{key, label, description?}] 만 통과(비밀 아님)."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        entry = {"key": key, "label": str(item.get("label") or key).strip()}
        desc = item.get("description")
        if desc:
            entry["description"] = str(desc).strip()
        out.append(entry)
    return out


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
        "effect": row.effect,
        "config_version": row.config_version,
        "created_at": _iso(row.created_at),
    }


def _public_skill(row: ChatSkill) -> dict:
    return {
        "id": row.id,
        "scope": row.scope,
        "name": row.name,
        "description": row.description,
        "instructions": decrypt_chat_content(row.instructions) if row.instructions else "",
        "is_active": row.is_active,
        "created_at": _iso(row.created_at),
    }


def selection_fingerprint(item: dict) -> str:
    """Return a secret-free configuration identity suitable for encrypted run payloads."""
    material = {
        key: item.get(key)
        for key in (
            "id",
            "name",
            "url",
            "method",
            "transport",
            "auth_mode",
            "params_schema",
            "config_version",
            "effect",
        )
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def mcp_credential_versions(
    server_ids: list[int] | tuple[int, ...], *, user_id: str, project_id: str
) -> dict[int, int | None]:
    """Return the active credential epoch for manual or OAuth MCP authentication."""
    ids = [server_id for server_id in server_ids if isinstance(server_id, int)]
    if not ids:
        return {}
    factory = _require_db()
    try:
        async with factory() as session:
            servers = {
                row.id: row
                for row in (await session.execute(select(ChatMcpServer).where(ChatMcpServer.id.in_(ids)))).scalars()
            }
            manual = {
                row.mcp_server_id: row
                for row in (
                    await session.execute(
                        select(ChatMcpCredential).where(
                            (ChatMcpCredential.mcp_server_id.in_(ids))
                            & (ChatMcpCredential.owner_user_id == user_id)
                            & (ChatMcpCredential.owner_project_id == project_id)
                        )
                    )
                ).scalars()
            }
            oauth = {
                row.mcp_server_id: row
                for row in (
                    await session.execute(
                        select(ChatMcpOAuthConnection).where(
                            (ChatMcpOAuthConnection.mcp_server_id.in_(ids))
                            & (ChatMcpOAuthConnection.owner_user_id == user_id)
                            & (ChatMcpOAuthConnection.owner_project_id == project_id)
                        )
                    )
                ).scalars()
            }
            versions: dict[int, int | None] = {}
            for server_id, server in servers.items():
                if _mcp_auth_mode(server) == "oauth":
                    connection = oauth.get(server_id)
                    versions[server_id] = (
                        connection.credential_version if connection and connection.status == "active" else None
                    )
                elif credential := manual.get(server_id):
                    versions[server_id] = None if credential.revoked_at is not None else credential.credential_version
            return versions
    except OperationalError as exc:
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def validated_frozen_selection(
    snapshot: object, *, user_id: str, project_id: str
) -> tuple[tuple[int, ...], tuple[int, ...], list[str]]:
    """Re-check a queued run's exact active configuration without widening selection."""
    if not isinstance(snapshot, dict):
        return (), (), ["run extension selection is unavailable"]
    selected_by_kind = {"tool": snapshot.get("tools"), "mcp": snapshot.get("mcp")}
    selected_mcp = selected_by_kind["mcp"]
    mcp_ids = (
        [item["id"] for item in selected_mcp if isinstance(item, dict) and isinstance(item.get("id"), int)]
        if isinstance(selected_mcp, list)
        else []
    )
    credential_versions = await mcp_credential_versions(mcp_ids, user_id=user_id, project_id=project_id)
    resolved: dict[str, tuple[int, ...]] = {"tool": (), "mcp": ()}
    warnings: list[str] = []
    for kind, selected in selected_by_kind.items():
        if not isinstance(selected, list):
            warnings.append(f"run {kind} selection is invalid")
            continue
        visible = await list_for_user(kind, user_id=user_id, project_id=project_id, active_only=True)
        current = {item["id"]: item for item in visible if isinstance(item.get("id"), int)}
        ids: list[int] = []
        for item in selected:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                warnings.append(f"run {kind} selection is invalid")
                continue
            now = current.get(item["id"])
            if now is None or item.get("config_fingerprint") != selection_fingerprint(now):
                warnings.append(f"selected {kind} changed or was revoked")
                continue
            if kind == "mcp":
                expected_version = item.get("credential_version")
                current_version = credential_versions.get(item["id"], 0)
                if not isinstance(expected_version, int) or expected_version != current_version:
                    warnings.append("selected MCP credential changed or was revoked")
                    continue
            ids.append(item["id"])
        resolved[kind] = tuple(ids)
    return resolved["tool"], resolved["mcp"], warnings


_PUBLIC = {"mcp": _public_mcp, "tool": _public_tool, "skill": _public_skill}


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
            if fields["transport"] not in _MCP_TRANSPORTS:
                raise ExtensionValidationError("transport 는 http(streamable HTTP)만 지원합니다")
            row.transport = fields["transport"]
        if "url" in fields:
            url = (fields["url"] or "").strip()
            if url and not url.lower().startswith("https://"):
                raise ExtensionValidationError("url 은 https:// 로 시작하는 원격 주소여야 합니다")
            row.url = url or None
            if _is_notion_mcp_url(row.url):
                row.auth_mode = "oauth"
        if "headers" in fields:
            # 헤더 값은 인증 시크릿(Bearer/API key)일 수 있으므로 AES-256-GCM 으로 암호화 저장.
            headers = fields["headers"]
            if headers is None:
                pass  # 미지정(field 없음과 동일 취급) = 기존 유지
            elif not isinstance(headers, dict):
                raise ExtensionValidationError("headers 는 문자열 값의 객체여야 합니다")
            elif not headers:
                # 명시적 빈 dict = 전체 삭제.
                row.encrypted_headers = None
                row.headers = None
            else:
                # 기존 헤더 위에 per-key overlay: 마스킹 sentinel(• 만) 값은 기존 유지, 실제 값은 교체/추가.
                # (마스킹 값 재전송으로 다른 헤더가 유실되지 않도록.)
                merged = dict(_decrypt_headers(row, fail_closed=True))
                for k, v in headers.items():
                    if not isinstance(v, str):
                        continue
                    key = str(k)
                    if set(v) == {"•"}:  # 마스킹 표시 = 변경 없음
                        continue
                    if v:  # 실제 값 = 교체/추가
                        merged[key] = v
                if merged:
                    row.encrypted_headers = encrypt_llm_provider_key(json.dumps(merged, ensure_ascii=False))
                    row.headers = None  # 레거시 plaintext 컬럼은 비운다
                else:
                    row.encrypted_headers = None
                    row.headers = None
        if "auth_requirements" in fields:
            req = fields["auth_requirements"]
            if req is None:
                row.auth_requirements = None
                cleaned = []
            elif isinstance(req, list):
                cleaned = _clean_requirements(req)
                row.auth_requirements = cleaned or None
            else:
                raise ExtensionValidationError("auth_requirements 는 [{key, label}] 리스트여야 합니다")
            if _mcp_auth_mode(row) != "oauth":
                row.auth_mode = "headers" if cleaned else "none"
    elif kind == "skill":
        if "name" in fields and fields["name"]:
            row.name = str(fields["name"]).strip()
        if "description" in fields:
            row.description = (str(fields["description"]).strip() or None) if fields["description"] else None
        if "instructions" in fields and fields["instructions"] is not None:
            text = str(fields["instructions"]).strip()
            if not text:
                raise ExtensionValidationError("스킬 지침(instructions)은 비어 있을 수 없습니다")
            if len(text) > 20000:
                raise ExtensionValidationError("스킬 지침이 너무 깁니다(최대 20000자)")
            row.instructions = encrypt_chat_content(text)
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
        # 선택적 확장 목록 — 전역 circuit breaker 를 열지 않는다(스키마 미적용/일시 실패가
        # 핵심 채팅 엔드포인트까지 503 으로 블랙아웃시키는 연쇄 방지). 진짜 DB 다운은 핵심 쿼리가 감지.
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def list_for_user(
    kind: str,
    *,
    user_id: str,
    project_id: str,
    active_only: bool = False,
    reveal_secrets: bool = False,
) -> list[dict]:
    """사용자용 — 활성 global + 본인 user 스코프.

    reveal_secrets=True 는 MCP 실행 경로(tool_runtime) 전용으로, 복호화된 실제
    인증 헤더를 포함한 dict 를 반환한다. API 응답으로는 절대 노출하지 말 것.
    """
    model = _model(kind)
    factory = _require_db()
    serialize = _reveal_mcp if (reveal_secrets and kind == "mcp") else _PUBLIC[kind]
    try:
        async with factory() as session:
            stmt = select(model).where(
                ((model.scope == "global") & (model.is_active.is_(True)))
                | ((model.scope == "user") & (model.owner_user_id == user_id) & (model.owner_project_id == project_id))
            )
            if active_only:
                stmt = stmt.where(model.is_active.is_(True))
            rows = (await session.execute(stmt.order_by(model.id))).scalars().all()
            return [serialize(r) for r in rows]
    except OperationalError as exc:
        # 선택적 확장 목록 — 전역 circuit breaker 를 열지 않는다(스키마 미적용/일시 실패가
        # 핵심 채팅(conversations 등)까지 503 으로 블랙아웃시키는 연쇄 방지). 진짜 DB 다운은 핵심 쿼리가 감지.
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
    if kind == "mcp" and not (fields.get("url") or "").strip():
        raise ExtensionValidationError("원격 MCP 서버는 url 이 필수입니다")
    if kind == "skill" and not (fields.get("instructions") or "").strip():
        raise ExtensionValidationError("스킬은 지침(instructions)이 필수입니다")

    # 스키마 NOT NULL 컬럼 기본값 — _apply_fields 가 덮어쓴다.
    _required_defaults = {
        "tool": {"description": "", "url": ""},
        "skill": {"instructions": ""},
    }
    row = model(
        scope=scope,
        owner_user_id=(owner_user_id if scope == "user" else None),
        owner_project_id=(owner_project_id if scope == "user" else None),
        **_required_defaults.get(kind, {}),
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
            if kind in {"mcp", "tool"}:
                row.config_version += 1
            await session.flush()
            return _PUBLIC[kind](row)
    except IntegrityError as exc:
        raise ExtensionValidationError("제약 위반") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


# ---------------------------------------------------------------------------
# 사용자별 MCP 인증 값 (chat_mcp_credentials) — 서버 auth_requirements 에 대응.
# 관리자는 요구사항만 선언하고, 각 사용자가 자신의 값을 채운다(암호화 저장).
# ---------------------------------------------------------------------------
async def _visible_mcp_server(session, server_id: int, *, user_id: str, project_id: str) -> ChatMcpServer:
    """사용자에게 보이는(활성 global 또는 본인 user 스코프) MCP 서버 로드. 아니면 404/403."""
    row = await session.get(ChatMcpServer, server_id)
    if row is None:
        raise ExtensionNotFound(f"MCP 서버 {server_id} 를 찾을 수 없습니다")
    if row.scope == "global":
        if not row.is_active:
            raise ExtensionForbidden("비활성 MCP 서버입니다")
    elif row.owner_user_id != user_id or row.owner_project_id != project_id:
        raise ExtensionForbidden("소유자가 아닙니다")
    return row


async def set_mcp_credentials(server_id: int, values: dict, *, user_id: str, project_id: str) -> dict:
    """사용자가 특정 MCP 서버의 인증 값을 저장(upsert). 요구사항에 선언된 key 만 허용(화이트리스트)."""
    if not isinstance(values, dict):
        raise ExtensionValidationError("values 는 객체여야 합니다")
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            server = await _visible_mcp_server(session, server_id, user_id=user_id, project_id=project_id)
            allowed = {r["key"] for r in _clean_requirements(server.auth_requirements)}
            if not allowed:
                raise ExtensionValidationError("이 서버는 사용자 인증 요구사항이 없습니다")
            # 마스킹 sentinel 은 기존 값 유지, 실제 값만 반영. 선언된 key 만.
            cred = await _get_credential_row(session, server_id, user_id, project_id, lock=True)
            existing = _decrypt_mcp_credential_values(cred, fail_closed=True)
            merged = dict(existing)
            for k, v in values.items():
                key = str(k)
                if key not in allowed or not isinstance(v, str):
                    continue
                if set(v) == {"•"}:  # 마스킹 = 변경 없음
                    continue
                if v:
                    merged[key] = v
            if merged:
                blob = encrypt_llm_provider_key(json.dumps(merged, ensure_ascii=False))
                if cred is None:
                    cred = ChatMcpCredential(
                        mcp_server_id=server_id,
                        owner_user_id=user_id,
                        owner_project_id=project_id,
                        encrypted_values=blob,
                        credential_version=1,
                    )
                    session.add(cred)
                else:
                    cred.encrypted_values = blob
                    cred.credential_version += 1
                    cred.revoked_at = None
            elif cred is not None and cred.revoked_at is None:
                cred.credential_version += 1
                cred.revoked_at = datetime.now(UTC)
            return _credential_status(server, merged)
    except IntegrityError as exc:
        raise ExtensionValidationError("제약 위반") from exc
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def get_mcp_credentials_status(server_id: int, *, user_id: str, project_id: str) -> dict:
    """서버 요구사항 + 사용자가 채운 key 목록(값은 노출 안 함)."""
    factory = _require_db()
    try:
        async with factory() as session:
            server = await _visible_mcp_server(session, server_id, user_id=user_id, project_id=project_id)
            values = _decrypt_mcp_credential_values(await _get_credential_row(session, server_id, user_id, project_id))
            return _credential_status(server, values)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def delete_mcp_credentials(server_id: int, *, user_id: str, project_id: str) -> None:
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            await _visible_mcp_server(session, server_id, user_id=user_id, project_id=project_id)
            cred = await _get_credential_row(session, server_id, user_id, project_id, lock=True)
            if cred is not None and cred.revoked_at is None:
                cred.credential_version += 1
                cred.revoked_at = datetime.now(UTC)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def mcp_all_credentials(*, user_id: str, project_id: str) -> dict[int, dict]:
    """실행 경로 전용 — 사용자의 모든 MCP 인증 값을 {server_id: {key: value}} 로 복호화 반환.

    저장소 장애/스키마 미적용 시 조용히 빈 dict(전역 circuit 을 오염시키지 않음)."""
    if not is_db_available():
        return {}
    factory = get_session_factory()
    if factory is None:
        return {}
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ChatMcpCredential).where(
                            (ChatMcpCredential.owner_user_id == user_id)
                            & (ChatMcpCredential.owner_project_id == project_id)
                            & (ChatMcpCredential.revoked_at.is_(None))
                        )
                    )
                )
                .scalars()
                .all()
            )
            return {r.mcp_server_id: _decrypt_mcp_credential_values(r, fail_closed=True) for r in rows}
    except ExtensionSecretUnavailable:
        raise
    except Exception:
        logger.warning("MCP 사용자 인증 값 로드 실패", exc_info=True)
        return {}


async def _get_credential_row(
    session, server_id: int, user_id: str, project_id: str, *, lock: bool = False
) -> ChatMcpCredential | None:
    stmt = select(ChatMcpCredential).where(
        (ChatMcpCredential.mcp_server_id == server_id)
        & (ChatMcpCredential.owner_user_id == user_id)
        & (ChatMcpCredential.owner_project_id == project_id)
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalars().first()


def _decrypt_mcp_credential_values(row: ChatMcpCredential | None, *, fail_closed: bool = False) -> dict:
    if row is None or row.revoked_at is not None or not row.encrypted_values:
        return {}
    try:
        data = json.loads(decrypt_llm_provider_key(row.encrypted_values))
        if not isinstance(data, dict):
            raise ValueError("decrypted MCP credentials are not an object")
        return data
    except Exception as exc:
        logger.warning("MCP 인증 값 복호 실패 id=%s", getattr(row, "id", "?"), exc_info=True)
        if fail_closed:
            raise ExtensionSecretUnavailable("MCP 사용자 인증 값을 복호화할 수 없습니다") from exc
        return {}


def _credential_status(server: ChatMcpServer, values: dict) -> dict:
    """요구사항별 충족 여부(값 미노출). filled=사용자가 채운 key."""
    reqs = _clean_requirements(server.auth_requirements)
    filled = {r["key"] for r in reqs if values.get(r["key"])}
    return {
        "mcp_server_id": server.id,
        "auth_requirements": reqs,
        "filled_keys": sorted(filled),
        "satisfied": all(r["key"] in filled for r in reqs),
    }


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
