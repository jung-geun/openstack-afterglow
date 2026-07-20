"""툴 런타임 — 내장 툴(tools.py) + 동적 커스텀 HTTP 툴 + MCP 서버 툴을 합쳐 그래프에 제공한다.

대화별 선택(ToolContext.selected_tool_ids/selected_mcp_ids)으로 노출 대상을 필터한다.
- None=활성 전체(하위호환), []=없음, [id...]=해당 항목만. 내장 툴은 항상 노출(플랫폼 툴).
커스텀 툴은 SSRF 가드 후 백엔드가 대리 HTTP 호출, MCP 툴은 mcp SDK 로 발견·실행(mcp_client).

⚠️ 보안:
- 커스텀 툴·MCP 는 호출자 컨텍스트(ctx)로 스코프된 것만 노출/실행. extensions_store 가 강제.
- 대리 호출/MCP 연결 전 ssrf.validate_url 로 내부/사설/메타데이터 IP 차단. redirect 미추적.
- 사용자 인증 토큰을 외부 URL 로 전달하지 않는다. 응답 크기 상한 + 타임아웃. 예외 미전파(안전한 문자열).
"""

from __future__ import annotations

import asyncio
import logging

from app.services.chat import mcp_client, ssrf, tools
from app.services.chat.tools import ToolContext

logger = logging.getLogger(__name__)

_MAX_RESPONSE_CHARS = 4000
_MCP_PREFIX = "mcp__"  # litellm 툴 이름: mcp__{server_id}__{tool_name}


def _selected(items: list[dict], selected_ids: tuple[int, ...] | None) -> list[dict]:
    """selected_ids 가 None 이면 전체, 아니면 id 가 포함된 것만."""
    if selected_ids is None:
        return items
    allow = set(selected_ids)
    return [it for it in items if it.get("id") in allow]


async def _load_custom(ctx: ToolContext) -> list[dict]:
    """호출자에게 노출되는 활성 커스텀 툴(global + 본인) — 선택 필터 적용. 저장소 장애 시 []."""
    from app.services.chat import extensions_store as es

    try:
        items = await es.list_for_user("tool", user_id=ctx.user_id, project_id=ctx.project_id, active_only=True)
    except Exception:
        logger.warning("커스텀 툴 로드 실패 — 내장 툴만 사용", exc_info=True)
        return []
    return _selected(items, ctx.selected_tool_ids)


async def _load_mcp(ctx: ToolContext) -> list[dict]:
    """호출자에게 노출되는 활성 MCP 서버 — 선택 필터 적용. 저장소 장애 시 []."""
    from app.services.chat import extensions_store as es

    try:
        items = await es.list_for_user("mcp", user_id=ctx.user_id, project_id=ctx.project_id, active_only=True)
    except Exception:
        logger.warning("MCP 서버 로드 실패", exc_info=True)
        return []
    return _selected(items, ctx.selected_mcp_ids)


def _custom_schema(tool_def: dict) -> dict:
    params = tool_def.get("params_schema") or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool_def["name"],
            "description": tool_def.get("description") or tool_def["name"],
            "parameters": params,
        },
    }


def _mcp_schema(server_id: int, tool: dict) -> dict:
    """MCP 툴 → litellm function 스키마. 이름에 server_id 를 접두해 실행 시 라우팅."""
    return {
        "type": "function",
        "function": {
            "name": f"{_MCP_PREFIX}{server_id}__{tool['name']}",
            "description": tool.get("description") or tool["name"],
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        },
    }


async def context_tool_schemas(ctx: ToolContext) -> list[dict]:
    """litellm 에 전달할 스키마 — 내장 + 선택된 커스텀 + 선택된 MCP 툴."""
    schemas = list(tools.tool_schemas())
    for t in await _load_custom(ctx):
        schemas.append(_custom_schema(t))
    # MCP: 선택된 서버마다 tool 목록을 발견(완료당 1회). 실패 서버는 조용히 건너뜀.
    for server in await _load_mcp(ctx):
        server_id = server.get("id")
        for tool in await mcp_client.list_tools(server):
            schemas.append(_mcp_schema(server_id, tool))
    return schemas


async def _execute_custom_http_tool(tool_def: dict, args: dict, ctx: ToolContext) -> str:
    """커스텀 HTTP 툴을 SSRF 가드 후 대리 호출. 항상 안전한 문자열 반환."""
    url = tool_def.get("url") or ""
    method = (tool_def.get("method") or "GET").upper()
    timeout = int(tool_def.get("timeout_seconds") or 10)
    try:
        await asyncio.to_thread(ssrf.validate_url, url)
    except ssrf.SsrfBlocked:
        return "허용되지 않은 URL 입니다(내부/사설 주소 차단)."
    except Exception:
        logger.warning("URL 검증 실패", exc_info=True)
        return "URL 검증에 실패했습니다."

    safe_args = args if isinstance(args, dict) else {}
    try:
        import httpx

        # 인증 헤더 미부착(사용자 토큰 유출 방지), redirect 미추적(내부 우회 차단).
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as cx:
            if method == "POST":
                resp = await cx.post(url, json=safe_args)
            else:
                resp = await cx.get(url, params=safe_args)
        body = (resp.text or "")[:_MAX_RESPONSE_CHARS]
        return f"[{resp.status_code}] {body}"
    except Exception:
        logger.warning("커스텀 툴 HTTP 호출 실패 name=%s", tool_def.get("name"), exc_info=True)
        return "툴 호출 중 오류가 발생했습니다."


async def _execute_mcp_tool(name: str, args: dict, ctx: ToolContext) -> str:
    """mcp__{server_id}__{tool} 을 파싱해 해당 MCP 서버에서 실행. 항상 안전한 문자열."""
    rest = name[len(_MCP_PREFIX) :]
    server_part, _, tool_name = rest.partition("__")
    if not tool_name:
        return f"알 수 없는 MCP 툴입니다: {name}"
    try:
        server_id = int(server_part)
    except ValueError:
        return f"알 수 없는 MCP 툴입니다: {name}"
    servers = {s.get("id"): s for s in await _load_mcp(ctx)}
    server = servers.get(server_id)
    if server is None:
        return "선택되지 않았거나 접근 불가한 MCP 서버입니다."
    return await mcp_client.call_tool(server, tool_name, args if isinstance(args, dict) else {})


async def context_execute(name: str, args: dict, ctx: ToolContext) -> str:
    """이름으로 툴 실행 — 내장 → 커스텀 → MCP. 항상 문자열."""
    if name.startswith(_MCP_PREFIX):
        return await _execute_mcp_tool(name, args, ctx)
    if name in tools._TOOL_BY_NAME:
        return await tools.execute_tool(name, args, ctx)
    customs = {t["name"]: t for t in await _load_custom(ctx)}
    if name in customs:
        return await _execute_custom_http_tool(customs[name], args, ctx)
    return f"알 수 없는 툴입니다: {name}"
