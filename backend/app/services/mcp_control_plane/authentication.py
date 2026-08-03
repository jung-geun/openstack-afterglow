"""Verified inbound MCP principals; browser and chat API tokens are never accepted."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import get_session_factory
from app.services.mcp_control_plane.authority import (
    McpAuthorityError,
    McpGrantNotFoundError,
    grant_scopes,
    resolve_personal_token,
)
from app.services.mcp_control_plane.oauth import McpOAuthUrls
from app.services.mcp_control_plane.oauth_authority import McpOAuthAuthorityError, resolve_oauth_access_token


class McpAuthenticationError(RuntimeError):
    """Authentication failed without exposing grant or credential state."""


@dataclass(frozen=True)
class McpPrincipal:
    grant_id: str
    user_id: str
    project_id: str
    credential_epoch: int
    scopes: frozenset[str]
    source: str
    selection_generation: int | None = None

    @property
    def can_write(self) -> bool:
        return "mcp:write" in self.scopes


def _factory() -> async_sessionmaker:
    factory = get_session_factory()
    if factory is None:
        raise McpAuthenticationError("MCP authority storage is unavailable")
    return factory


async def verify_mcp_bearer(raw_token: str, *, urls: McpOAuthUrls) -> McpPrincipal:
    """Accept exactly Afterglow PATs and exact-audience OAuth access tokens."""
    if not isinstance(raw_token, str) or not raw_token or raw_token.startswith(("sk-afgl-", "Bearer ")):
        raise McpAuthenticationError("MCP bearer token is invalid")
    try:
        async with _factory()() as session, session.begin():
            if raw_token.startswith("mcp-afgl-"):
                grant = await resolve_personal_token(session, raw_token)
                scopes = frozenset(grant_scopes(grant.access_level))
                source = "personal_token"
            else:
                grant, oauth_scopes = await resolve_oauth_access_token(
                    session, raw_token=raw_token, resource=urls.resource
                )
                scopes = frozenset(oauth_scopes)
                source = "oauth"
    except (McpAuthorityError, McpGrantNotFoundError, McpOAuthAuthorityError) as exc:
        raise McpAuthenticationError("MCP bearer token is invalid") from exc
    return McpPrincipal(
        grant_id=str(grant.id),
        user_id=grant.owner_user_id,
        project_id=grant.owner_project_id,
        credential_epoch=grant.credential_epoch,
        scopes=scopes,
        source=source,
    )
