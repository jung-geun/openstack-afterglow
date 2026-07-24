"""MCP streamable-HTTP transport hardening tests."""

from __future__ import annotations

import httpx
import pytest

from app.services.chat import mcp_client, ssrf


def test_open_rejects_legacy_sse_and_non_https():
    with pytest.raises(ValueError, match="streamable HTTP"):
        mcp_client._open({"transport": "sse", "url": "https://mcp.example"})
    with pytest.raises(ValueError, match="HTTPS"):
        mcp_client._open({"transport": "http", "url": "http://mcp.example"})


def test_content_result_uses_bounded_display_projection():
    class _Text:
        text = "x" * (mcp_client._MAX_RESULT_CHARS + 1)

    class _Result:
        content = [_Text()]

    assert mcp_client._content_to_str(_Result()) == "x" * mcp_client._MAX_RESULT_CHARS


def test_open_passes_hardened_factory_to_mcp_sdk(monkeypatch):
    captured: dict = {}

    def fake_streamablehttp_client(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return "context-manager"

    import mcp.client.streamable_http as streamable_http

    monkeypatch.setattr(streamable_http, "streamablehttp_client", fake_streamablehttp_client)
    assert (
        mcp_client._open(
            {"transport": "streamable_http", "url": "https://mcp.example/api", "headers": {"Authorization": "Bearer x"}}
        )
        == "context-manager"
    )
    assert captured["url"] == "https://mcp.example/api"
    assert captured["headers"] == {"Authorization": "Bearer x"}
    assert captured["httpx_client_factory"] is mcp_client._safe_http_client


async def test_mcp_http_factory_uses_pinned_transport_and_identity_encoding():
    client = mcp_client._safe_http_client({"Accept-Encoding": "gzip", "Authorization": "Bearer x"})
    try:
        assert isinstance(client._transport, ssrf.SafeAsyncTransport)
        assert client.headers["accept-encoding"] == "identity"
        assert client.follow_redirects is False
        assert client.trust_env is False
        assert client.timeout == httpx.Timeout(mcp_client._TIMEOUT_SECONDS)
    finally:
        await client.aclose()
