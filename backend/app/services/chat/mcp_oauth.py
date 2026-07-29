"""Per-user OAuth 2.1 connections for remote streamable-HTTP MCP servers.

The browser receives only an authorization URL. PKCE, state, tokens, and dynamic-client
credentials remain server-held and encrypted with the existing LLM provider-key domain.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import get_settings
from app.database import get_session_factory, mark_db_unhealthy
from app.models.chat_db import ChatMcpOAuthConnection, ChatMcpOAuthRequest, ChatMcpServer
from app.services.chat import ssrf
from app.services.chat.extensions_store import (
    ChatStorageUnavailable,
    ExtensionForbidden,
    ExtensionNotFound,
    ExtensionSecretUnavailable,
    _is_notion_mcp_url,
)
from app.services.k3s_crypto import decrypt_llm_provider_key, encrypt_llm_provider_key

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15
_MAX_RESPONSE_BYTES = 64 * 1024
_REQUEST_LIFETIME = timedelta(minutes=10)
_REFRESH_SKEW = timedelta(seconds=60)


INITIATOR_COOKIE = "afterglow_mcp_oauth_initiator"


def _verify_initiator_nonce(payload: dict[str, Any], initiator_nonce: str | None) -> None:
    expected_hash = payload.get("initiator_nonce_hash")
    if (
        not isinstance(initiator_nonce, str)
        or not isinstance(expected_hash, str)
        or not hmac.compare_digest(_hash(initiator_nonce), expected_hash)
    ):
        raise McpOAuthError("OAuth callback was not initiated by this browser")


class McpOAuthError(ValueError):
    """A safe, user-actionable remote OAuth failure."""


def _now() -> datetime:
    return datetime.now(UTC)


def _is_expired(expires_at: datetime) -> bool:
    # MariaDB returns DATETIME columns without tzinfo even when SQLAlchemy declares
    # timezone=True. OAuth expiry is stored and compared as UTC.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= _now()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _https_url(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise McpOAuthError(f"OAuth {field} is invalid")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise McpOAuthError(f"OAuth {field} is invalid") from exc
    if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise McpOAuthError(f"OAuth {field} must use HTTPS")
    return urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))


def _callback_url() -> str:
    settings = get_settings()
    configured = getattr(settings, "chat_mcp_oauth_callback_url", "")
    if isinstance(configured, str) and configured.strip():
        parsed = urlsplit(_https_url(configured.strip(), field="configured callback URL"))
        if parsed.query:
            raise McpOAuthError("OAuth configured callback URL must not include a query")
        return urlunsplit(("https", parsed.netloc, parsed.path or "/", "", ""))
    # Deployments commonly reverse-proxy the API behind the configured frontend origin.
    raw = (settings.public_api_base or settings.frontend_base_url).strip().rstrip("/")
    return f"{_https_url(raw, field='callback base').rstrip('/')}/api/v1/chat/mcp-oauth/callback"


def _well_known(origin: str, name: str) -> str:
    parsed = urlsplit(_https_url(origin, field="metadata issuer"))
    return urlunsplit(("https", parsed.netloc, f"/.well-known/{name}", "", ""))


def _pkce_verifier() -> str:
    # RFC 7636 unreserved charset; token_urlsafe only emits URL-safe unreserved characters.
    return secrets.token_urlsafe(64)


def _pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _token_expiry(payload: dict[str, Any]) -> datetime | None:
    raw = payload.get("expires_in")
    if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw <= 0:
        return None
    return _now() + timedelta(seconds=min(float(raw), 365 * 24 * 60 * 60))


def _decrypt(blob: str) -> dict[str, Any]:
    try:
        payload = json.loads(decrypt_llm_provider_key(blob))
        if not isinstance(payload, dict):
            raise ValueError("OAuth payload is not an object")
        return payload
    except Exception as exc:
        raise ExtensionSecretUnavailable("MCP OAuth secret cannot be decrypted") from exc


def _encrypt(payload: dict[str, Any]) -> str:
    return encrypt_llm_provider_key(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=ssrf.SafeAsyncTransport(max_response_bytes=_MAX_RESPONSE_BYTES),
        timeout=httpx.Timeout(_TIMEOUT_SECONDS),
        follow_redirects=False,
        trust_env=False,
        headers={"Accept-Encoding": "identity", "Accept": "application/json"},
    )


async def _json_response(response: httpx.Response, *, operation: str) -> dict[str, Any]:
    if response.status_code < 200 or response.status_code >= 300:
        raise McpOAuthError(f"OAuth {operation} failed ({response.status_code})")
    try:
        payload = response.json()
    except ValueError as exc:
        raise McpOAuthError(f"OAuth {operation} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise McpOAuthError(f"OAuth {operation} returned invalid JSON")
    return payload


async def _discover(server_url: str) -> dict[str, Any]:
    """Discover authorization metadata only through the DNS-pinned outbound boundary."""
    protected_metadata_url = _well_known(server_url, "oauth-protected-resource")
    async with _http_client() as client:
        protected = await _json_response(
            await client.get(protected_metadata_url), operation="protected-resource discovery"
        )
        authorization_servers = protected.get("authorization_servers")
        if not isinstance(authorization_servers, list) or not authorization_servers:
            raise McpOAuthError("This MCP server does not advertise OAuth authorization metadata")
        issuer = _https_url(authorization_servers[0], field="authorization server")
        metadata = await _json_response(
            await client.get(_well_known(issuer, "oauth-authorization-server")),
            operation="authorization-server discovery",
        )
    authorization_endpoint = _https_url(metadata.get("authorization_endpoint"), field="authorization endpoint")
    token_endpoint = _https_url(metadata.get("token_endpoint"), field="token endpoint")
    registration_endpoint = _https_url(metadata.get("registration_endpoint"), field="registration endpoint")
    resource = protected.get("resource")
    if resource is not None:
        resource = _https_url(resource, field="protected resource")
    return {
        "authorization_endpoint": authorization_endpoint,
        "token_endpoint": token_endpoint,
        "registration_endpoint": registration_endpoint,
        "resource": resource or server_url,
    }


async def _register_client(metadata: dict[str, Any], callback_url: str) -> dict[str, str]:
    body = {
        "client_name": "Afterglow Chat",
        "redirect_uris": [callback_url],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    async with _http_client() as client:
        response = await client.post(metadata["registration_endpoint"], json=body)
        registered = await _json_response(response, operation="dynamic client registration")
    client_id = registered.get("client_id")
    if not isinstance(client_id, str) or not client_id:
        raise McpOAuthError("OAuth dynamic client registration returned no client ID")
    client_secret = registered.get("client_secret")
    if client_secret is not None and not isinstance(client_secret, str):
        raise McpOAuthError("OAuth dynamic client registration returned an invalid client secret")
    return {"client_id": client_id, "client_secret": client_secret or ""}


async def _visible_server(session, server_id: int, *, user_id: str, project_id: str) -> ChatMcpServer:
    server = await session.get(ChatMcpServer, server_id)
    if server is None:
        raise ExtensionNotFound(f"MCP 서버 {server_id} 를 찾을 수 없습니다")
    if server.scope == "global":
        if not server.is_active:
            raise ExtensionForbidden("비활성 MCP 서버입니다")
    elif server.owner_user_id != user_id or server.owner_project_id != project_id:
        raise ExtensionForbidden("소유자가 아닙니다")
    if not server.url:
        raise McpOAuthError("MCP server URL is unavailable")
    return server


async def begin(server_id: int, *, user_id: str, project_id: str, initiator_nonce: str) -> dict[str, str]:
    """Create an OAuth authorization request bound to one user, project, server, and browser."""
    if not isinstance(initiator_nonce, str) or len(initiator_nonce) < 32:
        raise McpOAuthError("OAuth initiator binding is invalid")
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 오류")
    try:
        async with factory() as session:
            server = await _visible_server(session, server_id, user_id=user_id, project_id=project_id)
            server_url = _https_url(server.url, field="MCP server URL")
        metadata = await _discover(server_url)
        callback_url = _callback_url()
        client = await _register_client(metadata, callback_url)
        verifier = _pkce_verifier()
        state = secrets.token_urlsafe(32)
        request_payload = {
            **metadata,
            **client,
            "code_verifier": verifier,
            "callback_url": callback_url,
            "initiator_nonce_hash": _hash(initiator_nonce),
        }
        async with factory() as session, session.begin():
            server = await _visible_server(session, server_id, user_id=user_id, project_id=project_id)
            # Notion is classified at configuration time. A successful standards discovery safely promotes a generic server.
            server.auth_mode = "oauth"
            request = ChatMcpOAuthRequest(
                id=str(uuid.uuid4()),
                state_hash=_hash(state),
                mcp_server_id=server.id,
                owner_user_id=user_id,
                owner_project_id=project_id,
                encrypted_payload=_encrypt(request_payload),
                status="pending",
                expires_at=_now() + _REQUEST_LIFETIME,
            )
            session.add(request)
        query = {
            "response_type": "code",
            "client_id": client["client_id"],
            "redirect_uri": callback_url,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "state": state,
            "resource": metadata["resource"],
        }
        separator = "&" if "?" in metadata["authorization_endpoint"] else "?"
        return {"authorization_url": f"{metadata['authorization_endpoint']}{separator}{urlencode(query)}"}
    except (ExtensionNotFound, ExtensionForbidden, ChatStorageUnavailable, ExtensionSecretUnavailable, McpOAuthError):
        raise
    except (httpx.HTTPError, ssrf.SsrfBlocked) as exc:
        raise McpOAuthError("OAuth discovery could not connect to the MCP server") from exc
    except (IntegrityError, OperationalError) as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def _set_request_status(state_hash: str, status: str) -> None:
    factory = get_session_factory()
    if factory is None:
        return
    try:
        async with factory() as session, session.begin():
            request = (
                (
                    await session.execute(
                        select(ChatMcpOAuthRequest)
                        .where(ChatMcpOAuthRequest.state_hash == state_hash)
                        .with_for_update()
                    )
                )
                .scalars()
                .first()
            )
            if request is not None and request.status == "processing":
                request.status = status
                request.completed_at = _now()
    except Exception:
        logger.warning("MCP OAuth request status update failed", exc_info=True)


async def complete(*, state: str, code: str | None, error: str | None, initiator_nonce: str | None) -> int:
    """Consume a callback once, exchange its code, and save an encrypted connection."""
    if not state or len(state) > 512:
        raise McpOAuthError("OAuth callback state is invalid")
    state_hash = _hash(state)
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 오류")
    processing = False
    try:
        async with factory() as session, session.begin():
            request = (
                (
                    await session.execute(
                        select(ChatMcpOAuthRequest)
                        .where(ChatMcpOAuthRequest.state_hash == state_hash)
                        .with_for_update()
                    )
                )
                .scalars()
                .first()
            )
            if request is None or request.status != "pending" or _is_expired(request.expires_at):
                if request is not None and request.status == "pending":
                    request.status = "expired"
                raise McpOAuthError("OAuth authorization request has expired or was already used")
            payload = _decrypt(request.encrypted_payload)
            nonce_rejected = False
            try:
                _verify_initiator_nonce(payload, initiator_nonce)
            except McpOAuthError:
                # Do not raise while the transaction is open: that would roll back this
                # terminal state and leave the authorization code replayable.
                request.status = "failed"
                request.completed_at = _now()
                nonce_rejected = True
            else:
                request.status = "processing"
                processing = True
                request_id = request.id
                server_id = request.mcp_server_id
                owner_user_id = request.owner_user_id
                owner_project_id = request.owner_project_id
        if nonce_rejected:
            raise McpOAuthError("OAuth callback was not initiated by this browser")
        if error:
            await _set_request_status(state_hash, "failed")
            raise McpOAuthError("Notion authorization was cancelled or denied")
        if not isinstance(code, str) or not code or len(code) > 4096:
            await _set_request_status(state_hash, "failed")
            raise McpOAuthError("OAuth callback did not include an authorization code")
        token_form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": payload["callback_url"],
            "client_id": payload["client_id"],
            "code_verifier": payload["code_verifier"],
            "resource": payload["resource"],
        }
        if payload.get("client_secret"):
            token_form["client_secret"] = payload["client_secret"]
        async with _http_client() as client:
            tokens = await _json_response(
                await client.post(payload["token_endpoint"], data=token_form), operation="token exchange"
            )
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise McpOAuthError("OAuth token exchange returned no access token")
        stored_tokens = {
            "access_token": access_token,
            "refresh_token": tokens.get("refresh_token") if isinstance(tokens.get("refresh_token"), str) else "",
            "client_id": payload["client_id"],
            "client_secret": payload.get("client_secret") or "",
            "token_endpoint": payload["token_endpoint"],
            "resource": payload["resource"],
        }
        expires_at = _token_expiry(tokens)
        async with factory() as session, session.begin():
            request = await session.get(ChatMcpOAuthRequest, request_id, with_for_update=True)
            if request is None or request.status != "processing":
                raise McpOAuthError("OAuth authorization request could not be completed")
            connection = (
                (
                    await session.execute(
                        select(ChatMcpOAuthConnection)
                        .where(
                            (ChatMcpOAuthConnection.mcp_server_id == server_id)
                            & (ChatMcpOAuthConnection.owner_user_id == owner_user_id)
                            & (ChatMcpOAuthConnection.owner_project_id == owner_project_id)
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .first()
            )
            if connection is None:
                connection = ChatMcpOAuthConnection(
                    id=str(uuid.uuid4()),
                    mcp_server_id=server_id,
                    owner_user_id=owner_user_id,
                    owner_project_id=owner_project_id,
                    encrypted_tokens=_encrypt(stored_tokens),
                    credential_version=1,
                    status="active",
                    expires_at=expires_at,
                )
                session.add(connection)
            else:
                connection.encrypted_tokens = _encrypt(stored_tokens)
                connection.credential_version += 1
                connection.status = "active"
                connection.expires_at = expires_at
            request.status = "completed"
            request.completed_at = _now()
        return server_id
    except McpOAuthError:
        if processing:
            await _set_request_status(state_hash, "failed")
        raise
    except (ChatStorageUnavailable, ExtensionSecretUnavailable):
        raise
    except (httpx.HTTPError, ssrf.SsrfBlocked) as exc:
        await _set_request_status(state_hash, "failed")
        raise McpOAuthError("OAuth token exchange could not be completed") from exc
    except (IntegrityError, OperationalError) as exc:
        mark_db_unhealthy()
        await _set_request_status(state_hash, "failed")
        raise ChatStorageUnavailable("chat DB 오류") from exc
    except Exception:
        await _set_request_status(state_hash, "failed")
        raise


async def status(server_id: int, *, user_id: str, project_id: str) -> dict[str, Any]:
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 오류")
    try:
        async with factory() as session:
            server = await _visible_server(session, server_id, user_id=user_id, project_id=project_id)
            connection = (
                (
                    await session.execute(
                        select(ChatMcpOAuthConnection).where(
                            (ChatMcpOAuthConnection.mcp_server_id == server.id)
                            & (ChatMcpOAuthConnection.owner_user_id == user_id)
                            & (ChatMcpOAuthConnection.owner_project_id == project_id)
                        )
                    )
                )
                .scalars()
                .first()
            )
            required = _is_notion_mcp_url(server.url) or getattr(server, "auth_mode", "none") == "oauth"
            return {
                "mcp_server_id": server.id,
                "required": required,
                "connected": bool(connection and connection.status == "active"),
                "expires_at": connection.expires_at.isoformat() if connection and connection.expires_at else None,
            }
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def disconnect(server_id: int, *, user_id: str, project_id: str) -> None:
    factory = get_session_factory()
    if factory is None:
        raise ChatStorageUnavailable("chat DB 오류")
    try:
        async with factory() as session, session.begin():
            await _visible_server(session, server_id, user_id=user_id, project_id=project_id)
            connection = (
                (
                    await session.execute(
                        select(ChatMcpOAuthConnection)
                        .where(
                            (ChatMcpOAuthConnection.mcp_server_id == server_id)
                            & (ChatMcpOAuthConnection.owner_user_id == user_id)
                            & (ChatMcpOAuthConnection.owner_project_id == project_id)
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .first()
            )
            if connection and connection.status != "revoked":
                connection.status = "revoked"
                connection.credential_version += 1
                connection.expires_at = None
                connection.encrypted_tokens = _encrypt({})
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ChatStorageUnavailable("chat DB 오류") from exc


async def _refresh(connection_id: str, *, expected_version: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        return None
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": payload.get("client_id", ""),
        "resource": payload.get("resource", ""),
    }
    if payload.get("client_secret"):
        form["client_secret"] = payload["client_secret"]
    try:
        async with _http_client() as client:
            response = await client.post(payload["token_endpoint"], data=form)
            tokens = await _json_response(response, operation="token refresh")
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise McpOAuthError("OAuth token refresh returned no access token")
        refreshed = {
            **payload,
            "access_token": access_token,
            "refresh_token": tokens.get("refresh_token")
            if isinstance(tokens.get("refresh_token"), str)
            else refresh_token,
        }
        factory = get_session_factory()
        if factory is None:
            return None
        async with factory() as session, session.begin():
            connection = await session.get(ChatMcpOAuthConnection, connection_id, with_for_update=True)
            if connection is None or connection.status != "active":
                return None
            if connection.credential_version != expected_version:
                current = _decrypt(connection.encrypted_tokens)
                return current
            connection.encrypted_tokens = _encrypt(refreshed)
            connection.expires_at = _token_expiry(tokens)
        return refreshed
    except Exception:
        logger.info("MCP OAuth token refresh requires reconnection id=%s", connection_id, exc_info=True)
        return None


async def headers_for_user(*, user_id: str, project_id: str) -> dict[int, dict[str, str]]:
    """Return fresh bearer headers for active per-user OAuth connections; failures stay disconnected."""
    factory = get_session_factory()
    if factory is None:
        return {}
    try:
        async with factory() as session:
            connections = (
                (
                    await session.execute(
                        select(ChatMcpOAuthConnection).where(
                            (ChatMcpOAuthConnection.owner_user_id == user_id)
                            & (ChatMcpOAuthConnection.owner_project_id == project_id)
                            & (ChatMcpOAuthConnection.status == "active")
                        )
                    )
                )
                .scalars()
                .all()
            )
        result: dict[int, dict[str, str]] = {}
        for connection in connections:
            payload = _decrypt(connection.encrypted_tokens)
            if connection.expires_at is not None and connection.expires_at <= _now() + _REFRESH_SKEW:
                refreshed = await _refresh(
                    connection.id, expected_version=connection.credential_version, payload=payload
                )
                if refreshed is None:
                    continue
                payload = refreshed
            access_token = payload.get("access_token")
            if isinstance(access_token, str) and access_token:
                result[connection.mcp_server_id] = {"Authorization": f"Bearer {access_token}"}
        return result
    except ExtensionSecretUnavailable:
        raise
    except Exception:
        logger.warning("MCP OAuth connections could not be loaded", exc_info=True)
        return {}
