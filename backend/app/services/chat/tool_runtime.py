"""툴 런타임 — 내장 툴(tools.py) + 동적 커스텀 HTTP 툴 + MCP 서버 툴을 합쳐 그래프에 제공한다.

대화별 선택(ToolContext.selected_tool_ids/selected_mcp_ids)으로 노출 대상을 필터한다.
- None=활성 전체(하위호환), []=없음, [id...]=해당 항목만. 내장 툴은 항상 노출(플랫폼 툴).
커스텀 툴은 SSRF 가드 후 백엔드가 대리 HTTP 호출, MCP 툴은 mcp SDK 로 발견·실행(mcp_client).

⚠️ 보안:
- 커스텀 툴·MCP 는 호출자 컨텍스트(ctx)로 스코프된 것만 노출/실행. extensions_store 가 강제.
- 대리 호출/MCP 연결은 DNS-pinned SafeAsyncTransport로 내부/사설/메타데이터 IP와 rebinding을 차단한다. redirect 미추적.
- 사용자 인증 토큰을 외부 URL 로 전달하지 않는다. 스트리밍 응답 크기 상한 + 타임아웃. 예외 미전파(안전한 문자열).
"""

from __future__ import annotations

import json
import logging

from app.services.chat import advisor, mcp_client, ssrf, tools, web_fetch, web_search
from app.services.chat.tools import ToolContext

logger = logging.getLogger(__name__)

_MAX_RESPONSE_BYTES = 64 * 1024
_MAX_RESPONSE_CHARS = 4000
_MCP_PREFIX = "mcp__"  # litellm 툴 이름: mcp__{server_id}__{tool_name}
_MANAGED_SEARCH_TOOL = "managed_web_search"
_MANAGED_FETCH_TOOL = "managed_web_fetch"
_MAX_MANAGED_RESULT_BYTES = 48 * 1024


class ToolExecutionResult:
    """Internal tool result; `visible=False` keeps content out of message parts and SSE."""

    __slots__ = ("content", "usage", "visible", "warning_code")

    def __init__(
        self,
        content: str,
        *,
        visible: bool = True,
        usage: tuple[dict[str, object], ...] = (),
        warning_code: str | None = None,
    ) -> None:
        self.content = content
        self.visible = visible
        self.usage = usage
        self.warning_code = warning_code


_MANAGED_ADVISOR_TOOL = "managed_advisor"


async def _read_bounded_response(response) -> str:
    content_encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if content_encoding not in ("", "identity"):
        return "압축된 툴 응답은 허용되지 않습니다."
    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > _MAX_RESPONSE_BYTES:
            return "툴 응답이 허용 크기를 초과했습니다."
        content.extend(chunk)
    return content.decode(response.encoding or "utf-8", errors="replace")[:_MAX_RESPONSE_CHARS]


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
        # reveal_secrets=True: 실행에는 복호화된 실제 인증 헤더가 필요(API 응답용 마스킹 dict 아님).
        items = await es.list_for_user(
            "mcp", user_id=ctx.user_id, project_id=ctx.project_id, active_only=True, reveal_secrets=True
        )
    except Exception:
        logger.warning("MCP 서버 로드 실패", exc_info=True)
        return []
    # 사용자별 인증 값(Notion/Gmail 등)을 서버 기본 헤더 위에 병합. 요구사항 미충족 서버는 노출 스킵
    # (인증 없이 호출하면 어차피 실패 → LLM 이 깨진 툴을 시도하지 않도록 미리 제외).
    creds_by_server = await es.mcp_all_credentials(user_id=ctx.user_id, project_id=ctx.project_id)
    usable: list[dict] = []
    for server in items:
        if server.get("transport") != "http" or not str(server.get("url") or "").lower().startswith("https://"):
            logger.warning("MCP 서버 %s: 지원되지 않는 transport 또는 URL — 노출 스킵", server.get("id"))
            continue
        user_creds = creds_by_server.get(server.get("id")) or {}
        if user_creds:
            server["headers"] = {**(server.get("headers") or {}), **user_creds}
        reqs = server.get("auth_requirements") or []
        headers = server.get("headers") or {}
        if reqs and not all(r.get("key") in headers for r in reqs):
            logger.info("MCP 서버 %s: 사용자 인증 요구사항 미충족 — 노출 스킵", server.get("id"))
            continue
        usable.append(server)
    return _selected(usable, ctx.selected_mcp_ids)


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


def _truncate_utf8(value: object, maximum_bytes: int) -> str | None:
    if not isinstance(value, str):
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[:maximum_bytes].decode("utf-8", errors="ignore")


def _bounded_search_result(citations: list[web_search.SearchCitation]) -> str:
    sources: list[dict[str, str | None]] = []
    for citation in citations:
        candidate = {
            "url": _truncate_utf8(citation.url, 2_048),
            "title": _truncate_utf8(citation.title, 512),
            "snippet": _truncate_utf8(citation.snippet, 2_048),
        }
        encoded = json.dumps({"sources": [*sources, candidate]}, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if len(encoded) > _MAX_MANAGED_RESULT_BYTES:
            break
        sources.append(candidate)
    return json.dumps({"sources": sources}, ensure_ascii=False, separators=(",", ":"))


def _managed_schema(name: str, description: str, property_name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {property_name: {"type": "string"}},
                "required": [property_name],
                "additionalProperties": False,
            },
        },
    }


async def _managed_use_allowed(ctx: ToolContext, name: str, maximum: object) -> bool:
    if not isinstance(maximum, int) or maximum < 1:
        return False
    check = getattr(ctx.execution_hooks, "managed_tool_allowed", None)
    if check is None:
        return False
    return bool(await check(tool_name=name, maximum=maximum))


def _managed_usage(
    *,
    kind: str,
    price_key: str,
    unit: str,
    source: str,
    model_name: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "kind": kind,
        "price_key": price_key,
        "quantity": "1",
        "unit": unit,
        "source": source,
    }
    if model_name is not None:
        result["model_name"] = model_name
    return result


async def _execute_managed_search(args: dict, ctx: ToolContext) -> ToolExecutionResult:
    config = ctx.managed_search
    query = args.get("query") if isinstance(args, dict) else None
    if (
        not isinstance(config, dict)
        or not isinstance(query, str)
        or not (query := query.strip())
        or len(query) > 10_000
    ):
        return ToolExecutionResult("검색어가 올바르지 않습니다.")
    options = config.get("options")
    route = config.get("route")
    if not isinstance(options, dict) or not isinstance(route, dict):
        return ToolExecutionResult("관리형 웹 검색 설정이 올바르지 않습니다.")
    if not await _managed_use_allowed(ctx, _MANAGED_SEARCH_TOOL, options.get("max_uses")):
        return ToolExecutionResult("이 실행의 웹 검색 사용 한도에 도달했습니다.")
    location = options.get("approximate_location")
    country = (
        location.get("country") if isinstance(location, dict) and isinstance(location.get("country"), str) else None
    )
    try:
        citations = await web_search.search_with_route(
            query,
            route=route,
            context_size=str(options.get("context_size") or ""),
            allowed_domains=tuple(options.get("allowed_domains") or ()),
            blocked_domains=tuple(options.get("blocked_domains") or ()),
            country=country,
        )
    except web_search.ManagedSearchError:
        logger.warning("managed web search failed", exc_info=True)
        return ToolExecutionResult("웹 검색 공급자 호출에 실패했습니다.")
    context_size = str(options.get("context_size") or "")
    return ToolExecutionResult(
        _bounded_search_result(citations),
        usage=(
            _managed_usage(
                kind="web_search_requests",
                price_key="web_search_request_per_unit",
                unit="request",
                source="search",
            ),
            _managed_usage(
                kind="web_search_context",
                price_key=f"web_search_context_{context_size}_per_unit",
                unit="context",
                source="search",
            ),
        ),
    )


async def _execute_managed_fetch(args: dict, ctx: ToolContext) -> ToolExecutionResult:
    options = ctx.managed_fetch
    url = args.get("url") if isinstance(args, dict) else None
    if not isinstance(options, dict) or not isinstance(url, str) or not (url := url.strip()) or len(url) > 2_048:
        return ToolExecutionResult("가져올 URL이 올바르지 않습니다.")
    if not await _managed_use_allowed(ctx, _MANAGED_FETCH_TOOL, options.get("max_uses")):
        return ToolExecutionResult("이 실행의 웹 가져오기 사용 한도에 도달했습니다.")
    try:
        document = await web_fetch.fetch_document(
            url,
            allowed_domains=tuple(options.get("allowed_domains") or ()),
            blocked_domains=tuple(options.get("blocked_domains") or ()),
        )
    except web_fetch.ManagedFetchError:
        logger.warning("managed web fetch failed", exc_info=True)
        return ToolExecutionResult("웹 페이지를 안전하게 가져오지 못했습니다.")
    return ToolExecutionResult(
        json.dumps(
            {
                "url": _truncate_utf8(document.url, 2_048),
                "title": _truncate_utf8(document.title, 512),
                "content_type": document.content_type,
                "text": _truncate_utf8(document.text, _MAX_MANAGED_RESULT_BYTES - 4_096),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        usage=(
            _managed_usage(
                kind="web_fetch_requests",
                price_key="web_fetch_request_per_unit",
                unit="request",
                source="fetch",
            ),
            _managed_usage(
                kind="web_fetch_context",
                price_key="web_fetch_context_per_unit",
                unit="context",
                source="fetch",
            ),
        ),
    )


async def _execute_managed_advisor(args: dict, ctx: ToolContext) -> ToolExecutionResult:
    config = ctx.managed_advisor
    goal = args.get("goal") if isinstance(args, dict) else None
    if not isinstance(config, dict) or not isinstance(goal, str) or not (goal := goal.strip()) or len(goal) > 10_000:
        return ToolExecutionResult("Advisor goal is invalid.", visible=False)
    route = config.get("route")
    options = config.get("options")
    if not isinstance(route, dict) or not isinstance(options, dict):
        return ToolExecutionResult("Advisor configuration is invalid.", visible=False)
    if not await _managed_use_allowed(ctx, _MANAGED_ADVISOR_TOOL, options.get("max_uses")):
        return ToolExecutionResult("Advisor use limit reached.", visible=False)
    try:
        result = await advisor.ask_with_route(
            route=route,
            goal=goal,
            visible_messages=list(ctx.advisor_visible_messages),
        )
    except advisor.AdvisorError:
        logger.warning("managed advisor failed", exc_info=True)
        return ToolExecutionResult("Advisor request failed.", visible=False, warning_code="advisor_call_failed")
    return ToolExecutionResult(
        result.advice,
        visible=False,
        usage=(
            _managed_usage(
                kind="advisor_input_tokens",
                price_key="advisor_input_price_per_token",
                unit="token",
                source="advisor",
                model_name=str(route.get("model_name") or ""),
            )
            | {"quantity": str(result.prompt_tokens)},
            _managed_usage(
                kind="advisor_output_tokens",
                price_key="advisor_output_price_per_token",
                unit="token",
                source="advisor",
                model_name=str(route.get("model_name") or ""),
            )
            | {"quantity": str(result.completion_tokens)},
        ),
    )


def _visible_result(value: str | ToolExecutionResult) -> ToolExecutionResult:
    return value if isinstance(value, ToolExecutionResult) else ToolExecutionResult(value)


async def context_tool_schemas(ctx: ToolContext) -> list[dict]:
    """litellm 에 전달할 schemas — builtin, managed, selected custom and MCP tools."""
    if not ctx.tools_enabled:
        return []
    schemas = list(tools.tool_schemas())
    if ctx.managed_search is not None:
        schemas.append(
            _managed_schema(_MANAGED_SEARCH_TOOL, "Search the public web through the selected provider.", "query")
        )
    if ctx.managed_fetch is not None:
        schemas.append(_managed_schema(_MANAGED_FETCH_TOOL, "Fetch a permitted public HTTPS document.", "url"))
    if ctx.managed_advisor is not None:
        schemas.append(_managed_schema(_MANAGED_ADVISOR_TOOL, "Ask the selected advisor for private analysis.", "goal"))
    for tool_def in await _load_custom(ctx):
        schemas.append(_custom_schema(tool_def))
    for server in await _load_mcp(ctx):
        server_id = server.get("id")
        for tool_def in await mcp_client.list_tools(server):
            schemas.append(_mcp_schema(server_id, tool_def))
    return schemas


async def _execute_custom_http_tool(tool_def: dict, args: dict, ctx: ToolContext) -> str:
    """커스텀 HTTP 툴을 SSRF 가드 후 대리 호출. 항상 안전한 문자열 반환."""
    url = tool_def.get("url") or ""
    method = (tool_def.get("method") or "GET").upper()
    timeout = int(tool_def.get("timeout_seconds") or 10)

    safe_args = args if isinstance(args, dict) else {}
    try:
        import httpx

        # 인증 헤더 미부착(사용자 토큰 유출 방지), redirect 미추적(내부 우회 차단).
        async with httpx.AsyncClient(
            transport=ssrf.SafeAsyncTransport(),
            headers={"Accept-Encoding": "identity"},
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as cx:
            request_kwargs = {"json": safe_args} if method == "POST" else {"params": safe_args}
            request_method = "POST" if method == "POST" else "GET"
            async with cx.stream(request_method, url, **request_kwargs) as response:
                body = await _read_bounded_response(response)
                return f"[{response.status_code}] {body}"
    except ssrf.SsrfBlocked:
        return "허용되지 않은 URL 입니다(내부/사설 주소 차단)."
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


async def context_execute_result(name: str, args: dict, ctx: ToolContext) -> ToolExecutionResult:
    """Execute a tool and preserve whether its result may become a user-visible part."""
    if not ctx.tools_enabled:
        return ToolExecutionResult("Tool execution is disabled by this run's policy.")
    if name == _MANAGED_SEARCH_TOOL:
        return _visible_result(await _execute_managed_search(args, ctx))
    if name == _MANAGED_FETCH_TOOL:
        return _visible_result(await _execute_managed_fetch(args, ctx))
    if name == _MANAGED_ADVISOR_TOOL:
        return await _execute_managed_advisor(args, ctx)
    if name.startswith(_MCP_PREFIX):
        return _visible_result(await _execute_mcp_tool(name, args, ctx))
    if name in tools._TOOL_BY_NAME:
        return _visible_result(await tools.execute_tool(name, args, ctx))
    customs = {t["name"]: t for t in await _load_custom(ctx)}
    if name in customs:
        return _visible_result(await _execute_custom_http_tool(customs[name], args, ctx))
    return ToolExecutionResult(f"알 수 없는 툴입니다: {name}")


async def context_execute(name: str, args: dict, ctx: ToolContext) -> str:
    """Compatibility string boundary for non-graph callers."""
    return (await context_execute_result(name, args, ctx)).content
