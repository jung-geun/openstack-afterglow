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

import hashlib
import json
import logging
import re
from uuid import NAMESPACE_URL, uuid5

from app.models.chat_contracts import TextPart
from app.services.chat import advisor, mcp_client, ssrf, tools, web_fetch, web_search
from app.services.chat.agent_protocol import ToolBinding, ToolDefinition
from app.services.chat.agent_protocol import ToolExecutionResult as V2ToolExecutionResult
from app.services.chat.tools import ToolContext
from app.services.mcp_control_plane import ledger as mcp_ledger
from app.services.mcp_control_plane import lumen as mcp_lumen
from app.services.mcp_control_plane import registry as mcp_registry

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


def v2_builtin_tool_bindings() -> dict[str, ToolBinding]:
    """Return immutable v2 bindings for the read-only built-in tool registry.

    The v2 graph dispatches these bindings through ``agent_runtime_v2`` so JSON
    schema validation runs before a handler receives model-supplied arguments.
    """

    bindings: dict[str, ToolBinding] = {}
    for tool in tools.TOOLS:

        async def execute(arguments: dict[str, object], context: object, *, builtin=tool) -> V2ToolExecutionResult:
            if not isinstance(context, ToolContext):
                return V2ToolExecutionResult(
                    status="failed",
                    model_content="Tool execution context is invalid.",
                    error_code="invalid_tool_context",
                )
            result = await builtin.handler(arguments, context)
            model_content = str(result)[:8_192]
            return V2ToolExecutionResult(
                status="completed",
                model_content=model_content,
                display=[TextPart(type="text", text=model_content)] if model_content else [],
            )

        definition = ToolDefinition(
            name=tool.name,
            description=tool.description,
            input_schema={**tool.parameters, "additionalProperties": False},
            effect="read",
            parallel_safe=True,
            source="builtin",
        )
        bindings[definition.name] = ToolBinding(definition=definition, execute=execute)
    return bindings


def _v2_provider_name(prefix: str, identifier: int, name: object) -> str:
    raw_name = str(name)
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", raw_name).strip("_") or "tool"
    digest = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}__{identifier}__{normalized[:96]}_{digest}"[:128]


def _v2_effect(value: object) -> str:
    return value if value in {"read", "workspace_write", "process", "external_mutation"} else "external_mutation"


def _v2_config_fingerprint(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _v2_destination_origin(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        hostname, _port, scheme = ssrf._parse_and_validate_url(value)
    except ssrf.SsrfBlocked:
        return None
    return f"{scheme}://{hostname}"


def _v2_result(value: str | ToolExecutionResult) -> V2ToolExecutionResult:
    legacy = _visible_result(value)
    model_content = legacy.content[:8_192]
    return V2ToolExecutionResult(
        status="completed",
        model_content=model_content,
        display=[TextPart(type="text", text=model_content)] if legacy.visible and model_content else [],
        usage_components={"components": list(legacy.usage)},
        error_code=legacy.warning_code,
    )


def _lumen_idempotency_key(*, run_id: str, tool_call_id: str) -> str:
    """Use the durable run and call identity so retries replay only that call."""
    return f"lumen-{uuid5(NAMESPACE_URL, f'afterglow:lumen:{run_id}:{tool_call_id}')}"


async def _lumen_registry_bindings(ctx: ToolContext) -> tuple[ToolBinding, ...]:
    """Expose only the selected grant's explicit consumer-cloud registry entries."""
    try:
        if ctx.lumen_snapshot_frozen:
            snapshot = mcp_lumen.frozen_snapshot(ctx.lumen_snapshot)
        else:
            snapshot = await mcp_lumen.selected_lumen_snapshot(user_id=ctx.user_id, project_id=ctx.project_id)
        if snapshot is None:
            return ()
        if snapshot.user_id != ctx.user_id or snapshot.project_id != ctx.project_id:
            return ()
        principal = await mcp_lumen.resolve_lumen_principal(snapshot)
    except mcp_lumen.McpLumenAuthorityError:
        return ()

    bindings: list[ToolBinding] = []
    for entry in mcp_registry.enabled_entries(principal):
        definition = ToolDefinition(
            name=entry.name,
            description=entry.description,
            input_schema={**entry.input_schema(), "additionalProperties": False},
            effect=entry.effect,
            parallel_safe=entry.effect == "read",
            source="managed",
        )
        config_fingerprint = _v2_config_fingerprint(
            {
                "grant_id": snapshot.grant_id,
                "credential_epoch": snapshot.credential_epoch,
                "selection_generation": snapshot.selection_generation,
                "registry_version": mcp_registry.REGISTRY_VERSION,
                "service_fingerprint": mcp_registry.enabled_service_fingerprint(),
                "tool_name": entry.name,
            }
        )

        async def execute(
            arguments: dict[str, object],
            context: object,
            *,
            registry_entry=entry,
            frozen_snapshot=snapshot,
        ) -> V2ToolExecutionResult:
            if (
                not isinstance(context, ToolContext)
                or context.user_id != frozen_snapshot.user_id
                or context.project_id != frozen_snapshot.project_id
            ):
                return V2ToolExecutionResult(
                    status="failed",
                    model_content="Cloud tool execution context is invalid.",
                    error_code="invalid_tool_context",
                )
            try:
                current_principal = await mcp_lumen.resolve_lumen_principal(frozen_snapshot)
                parsed = mcp_registry.parse_entry_arguments(registry_entry, arguments)
                normalized = parsed.model_dump(mode="json")
                cloud_context = mcp_registry.ConsumerCloudContext(principal=current_principal)
                if registry_entry.effect == "read":
                    try:
                        result = await mcp_registry.dispatch(cloud_context, entry=registry_entry, arguments=parsed)
                        payload = mcp_registry.output_payload(registry_entry, result)
                    except Exception as exc:
                        await mcp_ledger.record_read_invocation(
                            current_principal,
                            entry=registry_entry,
                            arguments=normalized,
                            status="failed",
                            error=str(exc),
                            source="lumen",
                        )
                        raise
                    await mcp_ledger.record_read_invocation(
                        current_principal,
                        entry=registry_entry,
                        arguments=normalized,
                        status="succeeded",
                        source="lumen",
                    )
                else:
                    if not context.run_id or not context.tool_call_id:
                        raise mcp_ledger.McpInvocationError("Lumen mutation requires a durable tool call")
                    claim = await mcp_ledger.claim_mutation(
                        current_principal,
                        entry=registry_entry,
                        arguments=normalized,
                        idempotency_key=_lumen_idempotency_key(
                            run_id=context.run_id,
                            tool_call_id=context.tool_call_id,
                        ),
                        source="lumen",
                    )
                    if claim.state == "replay":
                        assert claim.result is not None
                        payload = claim.result
                    elif claim.state in {"in_progress", "unknown", "failed"}:
                        raise mcp_ledger.McpInvocationError(claim.error or "Cloud mutation is unavailable")
                    else:
                        try:
                            await mcp_registry.build_mutation_preview(
                                cloud_context, entry=registry_entry, arguments=parsed
                            )
                        except Exception:
                            await mcp_ledger.fail_pre_dispatch(
                                current_principal,
                                invocation_id=claim.invocation_id,
                                error="Lumen pre-dispatch validation failed",
                                source="lumen",
                            )
                            raise
                        try:
                            current_principal = await mcp_lumen.resolve_lumen_principal(frozen_snapshot)
                        except Exception:
                            await mcp_ledger.fail_pre_dispatch(
                                current_principal,
                                invocation_id=claim.invocation_id,
                                error="Lumen delegated MCP selection changed before dispatch",
                                source="lumen",
                            )
                            raise
                        cloud_context = mcp_registry.ConsumerCloudContext(principal=current_principal)
                        await mcp_ledger.authorize_mutation_dispatch(
                            current_principal, invocation_id=claim.invocation_id, source="lumen"
                        )
                        try:
                            result = await mcp_registry.dispatch(cloud_context, entry=registry_entry, arguments=parsed)
                            payload = mcp_registry.output_payload(registry_entry, result)
                            await mcp_ledger.complete_mutation(
                                current_principal,
                                invocation_id=claim.invocation_id,
                                result=payload,
                                source="lumen",
                            )
                        except Exception:
                            try:
                                await mcp_ledger.complete_mutation(
                                    current_principal,
                                    invocation_id=claim.invocation_id,
                                    error="Lumen mutation outcome is unknown after dispatch authorization",
                                    source="lumen",
                                )
                            except mcp_ledger.McpInvocationError:
                                pass
                            raise
                content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                return V2ToolExecutionResult(
                    status="completed",
                    model_content=content,
                    display=[TextPart(type="text", text=content)],
                )
            except Exception:
                logger.warning("Lumen cloud registry call failed tool=%s", registry_entry.name, exc_info=True)
                return V2ToolExecutionResult(
                    status="failed",
                    model_content="Cloud control-plane call was denied or is unavailable.",
                    error_code="cloud_control_unavailable",
                )

        async def preview(
            arguments: dict[str, object],
            context: object,
            *,
            registry_entry=entry,
            frozen_snapshot=snapshot,
        ) -> dict[str, object]:
            if registry_entry.effect != "external_mutation":
                return {}
            if (
                not isinstance(context, ToolContext)
                or context.user_id != frozen_snapshot.user_id
                or context.project_id != frozen_snapshot.project_id
            ):
                raise ValueError("Cloud tool execution context is invalid")
            current_principal = await mcp_lumen.resolve_lumen_principal(frozen_snapshot)
            parsed = mcp_registry.parse_entry_arguments(registry_entry, arguments)
            plan = await mcp_registry.build_mutation_preview(
                mcp_registry.ConsumerCloudContext(principal=current_principal),
                entry=registry_entry,
                arguments=parsed,
            )
            detail = f"{plan.intended_transition}: {plan.resource_identity}" + (
                f" (current state: {plan.current_state})" if plan.current_state else ""
            )
            return {
                "preview": [TextPart(type="text", text=detail).model_dump(mode="json")],
                "expected_state_revision": None,
                "writer_fence": None,
            }

        bindings.append(
            ToolBinding(
                definition=definition,
                execute=execute,
                preview=preview if entry.effect == "external_mutation" else None,
                config_fingerprint=config_fingerprint,
            )
        )
    return tuple(bindings)


async def v2_tool_bindings(ctx: ToolContext) -> dict[str, ToolBinding]:
    """Resolve frozen-schema bindings without allowing dynamic names to collide.

    Custom tools and MCP methods receive provider-safe, numeric namespaces. Their
    original names and transport records stay captured only in the server-side
    binding closure.
    """

    bindings = v2_builtin_tool_bindings()

    def add(binding: ToolBinding) -> None:
        if binding.definition.name in bindings:
            raise ValueError(f"duplicate v2 tool name: {binding.definition.name}")
        bindings[binding.definition.name] = binding

    for binding in await _lumen_registry_bindings(ctx):
        add(binding)

    for custom in await _load_custom(ctx):
        identifier = custom.get("id")
        if not isinstance(identifier, int):
            continue
        destination_origin = _v2_destination_origin(custom.get("url"))
        if destination_origin is None:
            logger.warning("custom tool without a canonical destination excluded from v2 bindings id=%s", identifier)
            continue
        try:
            definition = ToolDefinition(
                name=_v2_provider_name("custom", identifier, custom.get("name")),
                description=str(custom.get("description") or custom.get("name") or "Custom HTTP tool"),
                input_schema={
                    **(custom.get("params_schema") or {"type": "object", "properties": {}}),
                    "additionalProperties": False,
                },
                effect=_v2_effect(custom.get("effect")),
                source="custom_http",
            )
        except (TypeError, ValueError):
            logger.warning("invalid custom tool excluded from v2 bindings id=%s", identifier)
            continue

        async def execute(arguments: dict[str, object], context: object, *, tool_def=custom) -> V2ToolExecutionResult:
            if not isinstance(context, ToolContext):
                return V2ToolExecutionResult(
                    status="failed",
                    model_content="Tool execution context is invalid.",
                    error_code="invalid_tool_context",
                )
            return _v2_result(await _execute_custom_http_tool(tool_def, arguments, context))

        add(
            ToolBinding(
                definition=definition,
                execute=execute,
                config_fingerprint=_v2_config_fingerprint(
                    {
                        "id": identifier,
                        "name": custom.get("name"),
                        "url": custom.get("url"),
                        "method": custom.get("method"),
                        "params_schema": custom.get("params_schema"),
                        "effect": custom.get("effect"),
                        "config_version": custom.get("config_version"),
                    }
                ),
                destination_origin=destination_origin,
            )
        )

    for server in await _load_mcp(ctx):
        identifier = server.get("id")
        if not isinstance(identifier, int):
            continue
        destination_origin = _v2_destination_origin(server.get("url"))
        if destination_origin is None:
            logger.warning("MCP server without a canonical destination excluded from v2 bindings server=%s", identifier)
            continue
        try:
            discovered = await mcp_client.list_tools(server)
        except Exception:
            logger.warning("MCP discovery failed for v2 bindings server=%s", identifier, exc_info=True)
            continue
        for method in discovered:
            if not isinstance(method, dict) or not isinstance(method.get("name"), str):
                continue
            try:
                definition = ToolDefinition(
                    name=_v2_provider_name("mcp", identifier, method["name"]),
                    description=str(method.get("description") or method["name"]),
                    input_schema={
                        **(method.get("input_schema") or {"type": "object", "properties": {}}),
                        "additionalProperties": False,
                    },
                    effect=_v2_effect((server.get("effect_overrides") or {}).get(method["name"])),
                    source="mcp",
                )
            except (TypeError, ValueError):
                logger.warning(
                    "invalid MCP tool excluded from v2 bindings server=%s name=%r", identifier, method.get("name")
                )
                continue

            async def execute(
                arguments: dict[str, object],
                context: object,
                *,
                mcp_server=server,
                method_name=method["name"],
            ) -> V2ToolExecutionResult:
                if not isinstance(context, ToolContext):
                    return V2ToolExecutionResult(
                        status="failed",
                        model_content="Tool execution context is invalid.",
                        error_code="invalid_tool_context",
                    )
                return _v2_result(await mcp_client.call_tool(mcp_server, method_name, arguments))

            add(
                ToolBinding(
                    definition=definition,
                    execute=execute,
                    config_fingerprint=_v2_config_fingerprint(
                        {
                            "id": identifier,
                            "url": server.get("url"),
                            "effect_overrides": server.get("effect_overrides"),
                            "config_version": server.get("config_version"),
                        }
                    ),
                    destination_origin=destination_origin,
                )
            )

    return bindings


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
    from app.services.chat import mcp_oauth

    try:
        # reveal_secrets=True: 실행에는 복호화된 실제 인증 헤더가 필요(API 응답용 마스킹 dict 아님).
        items = await es.list_for_user(
            "mcp", user_id=ctx.user_id, project_id=ctx.project_id, active_only=True, reveal_secrets=True
        )
        # OAuth access tokens are per user/project. Public and administrator-approved
        # sources never accept user-provided secret variables.
        oauth_headers_by_server = (
            await mcp_oauth.headers_for_user(user_id=ctx.user_id, project_id=ctx.project_id)
            if any(server.get("auth_mode") == "oauth" for server in items)
            else {}
        )
        expected_credential_versions = dict(ctx.expected_mcp_credential_versions or ())
        credential_versions = (
            await es.mcp_credential_versions(
                list(expected_credential_versions), user_id=ctx.user_id, project_id=ctx.project_id
            )
            if expected_credential_versions
            else {}
        )
    except es.ExtensionSecretUnavailable:
        logger.warning("MCP secrets cannot be decrypted; disabling MCP tools", exc_info=True)
        return []
    except Exception:
        logger.warning("MCP server load failed", exc_info=True)
        return []
    usable: list[dict] = []
    for server in items:
        if server.get("transport") != "http" or not str(server.get("url") or "").lower().startswith("https://"):
            logger.warning("MCP server %s uses an unsupported transport or URL", server.get("id"))
            continue
        server_id = server.get("id")
        if server.get("auth_mode") == "oauth":
            oauth_headers = oauth_headers_by_server.get(server_id)
            if not oauth_headers:
                logger.info("MCP server %s has no active OAuth connection", server_id)
                continue
            server["headers"] = {**(server.get("headers") or {}), **oauth_headers}
        server_id = server.get("id")
        if expected_credential_versions and (
            not isinstance(server_id, int)
            or expected_credential_versions.get(server_id) != credential_versions.get(server_id, 0)
        ):
            logger.info("MCP 서버 %s: 실행 중 인증 값이 변경되었거나 폐기됨 — 노출 스킵", server_id)
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
