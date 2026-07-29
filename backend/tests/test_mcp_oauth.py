from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import mcp as mcp_api
from app.services.mcp_control_plane.oauth import (
    McpOAuthError,
    oauth_urls,
    pkce_s256,
    redirect_uri_matches,
    require_exact_resource,
    validate_pkce_s256,
    validate_redirect_uris,
    validate_scopes,
)


def test_oauth_urls_require_https_production_public_base():
    urls = oauth_urls("https://api.example.test/", production=True)

    assert urls.resource == "https://api.example.test/api/v1/mcp"
    assert urls.issuer == "https://api.example.test/api/v1/mcp/oauth"
    assert urls.protected_resource_metadata.endswith("/.well-known/oauth-protected-resource/api/v1/mcp")
    with pytest.raises(McpOAuthError, match="HTTPS"):
        oauth_urls("http://api.example.test", production=True)


def test_resource_scope_and_pkce_are_exact_and_fail_closed():
    urls = oauth_urls("https://api.example.test", production=True)
    assert require_exact_resource(urls.resource, urls) == urls.resource
    with pytest.raises(McpOAuthError, match="exactly"):
        require_exact_resource(urls.resource + "/", urls)
    assert validate_scopes("mcp:read mcp:write") == ("mcp:read", "mcp:write")
    with pytest.raises(McpOAuthError, match="scope"):
        validate_scopes("mcp:write")

    verifier = "a" * 43
    challenge = pkce_s256(verifier)
    assert validate_pkce_s256(challenge, "S256") == challenge
    with pytest.raises(McpOAuthError, match="PKCE"):
        validate_pkce_s256(challenge, "plain")


def test_redirect_registration_allows_ip_loopback_dynamic_port_and_exact_path_query_only():
    assert validate_redirect_uris(
        ["https://client.example.test/oauth/callback", "http://127.0.0.1/callback?flow=desktop"]
    ) == (
        "https://client.example.test/oauth/callback",
        "http://127.0.0.1/callback?flow=desktop",
    )
    assert redirect_uri_matches(
        "http://127.0.0.1/callback?flow=desktop", "http://127.0.0.1:41337/callback?flow=desktop"
    )
    assert redirect_uri_matches("http://[::1]/callback", "http://[::1]:41337/callback")
    assert not redirect_uri_matches("http://127.0.0.1/callback", "http://127.0.0.1/other")
    assert not redirect_uri_matches("http://127.0.0.1/callback?a=1", "http://127.0.0.1/callback?a=2")
    with pytest.raises(McpOAuthError, match="IP-literal"):
        validate_redirect_uris(["http://localhost/callback"])
    with pytest.raises(McpOAuthError, match="credentials"):
        validate_redirect_uris(["http://127.0.0.1/callback#fragment"])
    with pytest.raises(McpOAuthError, match="IP-literal"):
        validate_redirect_uris(["https://*.example.test/callback"])
    with pytest.raises(McpOAuthError, match="credentials"):
        validate_redirect_uris(["https://user:pass@client.example.test/callback"])


@pytest.mark.asyncio
async def test_authenticated_consent_details_are_never_cacheable(monkeypatch):
    monkeypatch.setattr(mcp_api, "_require_enabled", lambda: None)
    monkeypatch.setattr(mcp_api, "_session_factory", lambda: object())
    monkeypatch.setattr(
        mcp_api,
        "load_consent_ticket",
        AsyncMock(
            return_value=SimpleNamespace(
                client_id="client-id",
                client_name="Example client",
                redirect_uri="https://client.example.test/callback",
                scopes=("mcp:read",),
                grant_deadline=datetime(2026, 8, 1, tzinfo=UTC),
            )
        ),
    )

    response = await mcp_api.get_oauth_consent(
        "ticket",
        token_info={"user_id": "user-a", "project_id": "project-a"},
    )

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert b"client-id" in response.body
