"""MCP 서버 연동 — 등록된 MCP 서버의 tool 을 발견(list)·실행(call).

우리 그래프는 자체 tool 루프(litellm tools)를 쓰므로 langchain-mcp-adapters 없이 mcp SDK 를 직접 쓴다.
transport: streamable HTTP only (legacy SSE·stdio 미지원 — 서버 프로세스 spawn 과 redirect-based auth forwarding을 방지).

⚠️ 보안:
- SafeAsyncTransport가 실제 socket을 DNS-pinned public address로 열고, redirect·env proxy·압축 응답을 거부한다.
- 모든 예외는 밖으로 던지지 않고 빈 목록/안전한 문자열 반환(MCP 장애가 채팅을 막지 않음).
- 연결·호출 타임아웃 + raw response byte 상한.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit

import httpx

from app.services.chat import ssrf

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15
_MAX_RESULT_CHARS = 6000
_MAX_TOOLS_PER_SERVER = 40
_MAX_RESPONSE_BYTES = 1024 * 1024


def _safe_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """Factory required by MCP's streamable transport; never inherit SDK defaults."""
    request_headers = dict(headers or {})
    request_headers["Accept-Encoding"] = "identity"
    return httpx.AsyncClient(
        transport=ssrf.SafeAsyncTransport(max_response_bytes=_MAX_RESPONSE_BYTES),
        headers=request_headers,
        timeout=timeout or httpx.Timeout(_TIMEOUT_SECONDS),
        follow_redirects=False,
        trust_env=False,
        auth=auth,
    )


def _open(server: dict):
    """Return a hardened streamable-HTTP MCP context manager."""
    transport = (server.get("transport") or "http").lower()
    if transport not in ("http", "streamable_http", "streamable-http"):
        raise ValueError("streamable HTTP MCP transport is required")
    url = server.get("url") or ""
    if urlsplit(url).scheme.lower() != "https":
        raise ValueError("MCP URL must use HTTPS")
    headers = server.get("headers") or {}
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in headers.items()
    ):
        raise ValueError("MCP headers must be string pairs")
    from mcp.client.streamable_http import streamablehttp_client

    return streamablehttp_client(
        url,
        headers=headers,
        timeout=_TIMEOUT_SECONDS,
        httpx_client_factory=_safe_http_client,
    )


def _content_to_str(result) -> str:
    """call_tool 결과의 content 블록들을 텍스트로. 상한 적용."""
    parts: list[str] = []
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    joined = "\n".join(parts) if parts else str(content)
    return joined[:_MAX_RESULT_CHARS]


async def list_tools(server: dict) -> list[dict]:
    """MCP 서버의 tool 목록 → [{name, description, input_schema}]. 실패 시 빈 목록."""

    async def _run() -> list[dict]:
        from mcp import ClientSession

        async with _open(server) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.list_tools()
                out: list[dict] = []
                for t in (res.tools or [])[:_MAX_TOOLS_PER_SERVER]:
                    out.append(
                        {
                            "name": t.name,
                            "description": getattr(t, "description", "") or "",
                            "input_schema": getattr(t, "inputSchema", None) or {"type": "object", "properties": {}},
                        }
                    )
                return out

    try:
        return await asyncio.wait_for(_run(), timeout=_TIMEOUT_SECONDS)
    except Exception:
        logger.warning("MCP list_tools 실패 name=%s", server.get("name"), exc_info=True)
        return []


async def call_tool(server: dict, tool_name: str, args: dict) -> str:
    """MCP tool 실행 → 결과 텍스트. 실패 시 안전한 문자열."""

    async def _run() -> str:
        from mcp import ClientSession

        async with _open(server) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool(tool_name, arguments=(args if isinstance(args, dict) else {}))
                return _content_to_str(res)

    try:
        return await asyncio.wait_for(_run(), timeout=_TIMEOUT_SECONDS)
    except Exception:
        logger.warning("MCP call_tool 실패 name=%s tool=%s", server.get("name"), tool_name, exc_info=True)
        return "MCP 도구 실행 중 오류가 발생했습니다."
