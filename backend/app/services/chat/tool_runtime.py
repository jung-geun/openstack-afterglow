"""툴 런타임 — 내장 툴(tools.py) + 동적 커스텀 HTTP 툴(extensions_store)을 합쳐

그래프에 제공한다. 커스텀 툴은 SSRF 가드 후 백엔드가 대리 HTTP 호출한다.

⚠️ 보안:
- 커스텀 툴은 호출자 컨텍스트(ctx)로 스코프된 것만 노출/실행(활성 global + 본인 것). extensions_store 가 강제.
- 대리 호출 전 ssrf.validate_url 로 내부/사설/메타데이터 IP 차단. redirect 미추적.
- 사용자 인증 토큰을 외부 URL 로 전달하지 않는다.
- 응답 크기 상한(4KB) + 타임아웃. 예외는 밖으로 던지지 않고 안전한 문자열 반환.
"""

from __future__ import annotations

import asyncio
import logging

from app.services.chat import ssrf, tools
from app.services.chat.tools import ToolContext

logger = logging.getLogger(__name__)

_MAX_RESPONSE_CHARS = 4000


async def _load_custom(ctx: ToolContext) -> list[dict]:
    """호출자에게 노출되는 활성 커스텀 툴(global + 본인). 저장소 장애 시 graceful []."""
    from app.services.chat import extensions_store as es

    try:
        return await es.list_for_user("tool", user_id=ctx.user_id, project_id=ctx.project_id, active_only=True)
    except Exception:
        logger.warning("커스텀 툴 로드 실패 — 내장 툴만 사용", exc_info=True)
        return []


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


async def context_tool_schemas(ctx: ToolContext) -> list[dict]:
    """litellm 에 전달할 스키마 — 내장 + 동적 커스텀."""
    schemas = list(tools.tool_schemas())
    for t in await _load_custom(ctx):
        schemas.append(_custom_schema(t))
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


async def context_execute(name: str, args: dict, ctx: ToolContext) -> str:
    """이름으로 툴 실행 — 내장 우선, 없으면 호출자 스코프 커스텀 툴. 항상 문자열."""
    if name in tools._TOOL_BY_NAME:
        return await tools.execute_tool(name, args, ctx)
    customs = {t["name"]: t for t in await _load_custom(ctx)}
    if name in customs:
        return await _execute_custom_http_tool(customs[name], args, ctx)
    return f"알 수 없는 툴입니다: {name}"
