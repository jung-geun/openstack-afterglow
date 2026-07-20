"""MCP 서버 연동 — 등록된 MCP 서버의 tool 을 발견(list)·실행(call).

우리 그래프는 자체 tool 루프(litellm tools)를 쓰므로 langchain-mcp-adapters 없이 mcp SDK 를 직접 쓴다.
transport: streamable_http(기본)·sse 지원(stdio 미지원 — 서버 프로세스 spawn 은 보안상 제외).

⚠️ 보안:
- 연결 전 ssrf.validate_url 로 내부/사설/메타데이터 IP 차단(사용자/관리자 등록 URL 신뢰 안 함).
- 모든 예외는 밖으로 던지지 않고 빈 목록/안전한 문자열 반환(MCP 장애가 채팅을 막지 않음).
- 연결·호출 타임아웃 + 응답 크기 상한.
"""

from __future__ import annotations

import asyncio
import logging

from app.services.chat import ssrf

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15
_MAX_TOOLS_PER_SERVER = 40
_MAX_RESULT_CHARS = 6000


def _open(server: dict):
    """transport 에 맞는 mcp 클라이언트 async context manager 반환. 미지원 시 ValueError."""
    transport = (server.get("transport") or "http").lower()
    url = server.get("url") or ""
    headers = server.get("headers") or {}
    if transport in ("http", "streamable_http", "streamable-http"):
        from mcp.client.streamable_http import streamablehttp_client

        return streamablehttp_client(url, headers=headers, timeout=_TIMEOUT_SECONDS)
    if transport == "sse":
        from mcp.client.sse import sse_client

        return sse_client(url, headers=headers, timeout=_TIMEOUT_SECONDS)
    raise ValueError(f"지원하지 않는 MCP transport: {transport}")


async def _validate(server: dict) -> bool:
    url = server.get("url") or ""
    if not url:
        return False
    try:
        await asyncio.to_thread(ssrf.validate_url, url)
        return True
    except ssrf.SsrfBlocked:
        logger.warning("MCP URL SSRF 차단 name=%s", server.get("name"))
        return False
    except Exception:
        logger.warning("MCP URL 검증 실패 name=%s", server.get("name"), exc_info=True)
        return False


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
    if not await _validate(server):
        return []

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
    if not await _validate(server):
        return "허용되지 않은 MCP 서버 URL 입니다."

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
