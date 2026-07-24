"""Phase 2 chat_engine — LangGraph + litellm 에이전트 루프(내부 툴, MCP 미포함).

설계 결정(2026-07-18):
- litellm_client 를 그대로 쓰고(ChatLiteLLM/langchain-community 미도입), LangGraph 는 그래프 구조·
  상태·스트리밍만 담당한다. 에이전트 루프(모델↔툴)는 노드 내부에서 돌린다.
- litellm 은 LangChain 모델이 아니므로 stream_mode="messages" 대신 **stream_mode="custom" +
  get_stream_writer()** 로 토큰/툴 이벤트를 emit 한다.
- 툴은 자체 루프로 실행: 스트리밍하며 텍스트 델타와 tool_call 델타를 누적하고, tool_call 이 있으면
  **테넌트 안전(tools.execute_tool, ToolContext)** 하게 실행 후 결과를 붙여 다음 턴으로 넘긴다.
- 멀티스텝(툴 호출로 여러 litellm 콜) usage 를 합산해 마지막에 1회 emit → 엔드포인트가 과금.
- 이벤트 계약: token / tool_call / usage / error → completions 엔드포인트가 SSE 로 중계.
- 대화 전사는 MySQL chat_messages(source of truth)에서 매 요청 로드해 messages 로 주입.
- 외부 MCP 서버 연동은 pydantic/uvicorn/httpx 핀 이동 필요(별도 결정) — 여기선 내부 툴만.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.services.chat import litellm_client, tool_runtime
from app.services.chat.checkpointer import chat_checkpointer
from app.services.chat.tools import ToolContext

logger = logging.getLogger(__name__)

_MAX_TOOL_STEPS = 4  # 툴 실행 라운드 상한(무한 루프 방지) — 초과 시 마지막 턴을 최종 답변으로

# Generic reasoning rejections are retried without the parameter.
_REASONING_UNSUPPORTED: set[str] = set()
# OpenAI Chat Completions models that require the explicit `none` value when tools are sent.
_TOOL_REASONING_EXPLICIT_NONE: set[str] = set()


class _BoundaryAbort(RuntimeError):
    """A durable hook detected an indeterminate external-call boundary."""


def _abort_code(payload: Any) -> str | None:
    if isinstance(payload, dict) and isinstance(payload.get("_boundary_abort"), str):
        return payload["_boundary_abort"]
    return None


def _is_tool_reasoning_conflict(error: Exception) -> bool:
    """OpenAI Chat Completions가 tool+기본 추론을 거부했는지 판별한다."""
    message = str(error).lower()
    return "function tools" in message and "reasoning_effort" in message


class ChatState(TypedDict, total=False):
    messages: list[dict]
    pending_tool_calls: list[dict]
    loop_count: int
    final_text: str
    citations: list[dict]
    usage: dict[str, int]
    tool_usage: list[dict[str, object]]
    model_failed: bool


def _delta(chunk) -> Any:
    choices = getattr(chunk, "choices", None)
    if choices is None and isinstance(chunk, dict):
        choices = chunk.get("choices")
    if not choices:
        return None
    first = choices[0]
    d = getattr(first, "delta", None)
    if d is None and isinstance(first, dict):
        d = first.get("delta")
    return d


def _delta_content(delta) -> str | None:
    content = getattr(delta, "content", None)
    if content is None and isinstance(delta, dict):
        content = delta.get("content")
    return content


def _delta_reasoning(delta) -> str | None:
    """추론 델타(reasoning_content) 추출 — litellm 이 provider 무관하게 정규화한 필드."""
    reasoning = getattr(delta, "reasoning_content", None)
    if reasoning is None and isinstance(delta, dict):
        reasoning = delta.get("reasoning_content")
    return reasoning if isinstance(reasoning, str) and reasoning else None


def _accumulate_tool_calls(delta, acc: dict[int, dict]) -> None:
    """스트리밍 tool_call 델타(index별 부분)를 acc 에 누적."""
    tcs = getattr(delta, "tool_calls", None)
    if tcs is None and isinstance(delta, dict):
        tcs = delta.get("tool_calls")
    if not tcs:
        return
    for tc in tcs:
        idx = getattr(tc, "index", None)
        if idx is None and isinstance(tc, dict):
            idx = tc.get("index")
        if idx is None:
            idx = 0
        entry = acc.setdefault(idx, {"id": None, "name": None, "args": ""})
        tc_id = getattr(tc, "id", None) or (tc.get("id") if isinstance(tc, dict) else None)
        if tc_id:
            entry["id"] = tc_id
        fn = getattr(tc, "function", None)
        if fn is None and isinstance(tc, dict):
            fn = tc.get("function")
        if fn is not None:
            name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else None)
            if name:
                entry["name"] = name
            args = getattr(fn, "arguments", None)
            if args is None and isinstance(fn, dict):
                args = fn.get("arguments")
            if args:
                entry["args"] += args


_CITATION_SNIPPET_CAP = 300  # 스니펫 저장/전송 상한(Perplexity 는 표 덤프 등 매우 길 수 있음)


def _get(obj, key):
    val = getattr(obj, key, None)
    if val is None and isinstance(obj, dict):
        val = obj.get(key)
    return val


def _is_http_url(url) -> bool:
    """http/https 만 출처로 허용(javascript:·data: 등 방어). 프론트가 다시 검증하지만 이중 방어."""
    return isinstance(url, str) and (url.startswith("http://") or url.startswith("https://"))


def _extract_citations(chunk, delta, acc: dict[str, dict]) -> None:
    """Normalize provider citations into stable web or document source records."""

    # search_results — rich web sources take precedence over bare URL citations.
    for item in _get(chunk, "search_results") or []:
        url = _get(item, "url")
        if not _is_http_url(url):
            continue
        snippet = _get(item, "snippet")
        acc[url] = {
            "source_kind": "web",
            "url": url,
            "title": _get(item, "title"),
            "snippet": (snippet[:_CITATION_SNIPPET_CAP] if isinstance(snippet, str) else None),
        }

    # Bare URL citations, emitted by several OpenAI-compatible providers.
    for citation in _get(chunk, "citations") or []:
        if _is_http_url(citation):
            acc.setdefault(citation, {"source_kind": "web", "url": citation, "title": None, "snippet": None})

    # LiteLLM's Anthropic-unified protocol attaches document citations to a
    # streaming delta's provider_specific_fields["citation"]. A non-stream
    # content-block shape is also accepted for replayed/provider test fixtures.
    def add_document_citation(citation: Any) -> None:
        index = _get(citation, "document_index")
        if not isinstance(index, int) or index < 0:
            return
        start = _get(citation, "start_char_index")
        end = _get(citation, "end_char_index")
        if not isinstance(start, int) or start < 0:
            start = None
        if not isinstance(end, int) or end < 0:
            end = None
        if (start is None) != (end is None) or (start is not None and end is not None and start > end):
            start = end = None
        snippet = _get(citation, "cited_text")
        key = f"document:{index}:{start if start is not None else ''}:{end if end is not None else ''}:{snippet or ''}"
        acc.setdefault(
            key,
            {
                "source_kind": "document",
                "document_index": index,
                "title": _get(citation, "document_title"),
                "snippet": snippet[:_CITATION_SNIPPET_CAP] if isinstance(snippet, str) else None,
                **({"start_index": start, "end_index": end} if start is not None else {}),
            },
        )

    provider_citation = _get(_get(delta, "provider_specific_fields") or {}, "citation")
    if provider_citation is not None:
        add_document_citation(provider_citation)
    for content_block in _get(chunk, "content") or []:
        for citation in _get(content_block, "citations") or []:
            add_document_citation(citation)

    # annotations(url_citation) — Gemini/OpenAI
    for annotation in _get(delta, "annotations") or []:
        url_citation = _get(annotation, "url_citation") or {}
        url = _get(url_citation, "url")
        if _is_http_url(url):
            acc.setdefault(
                url,
                {"source_kind": "web", "url": url, "title": _get(url_citation, "title"), "snippet": None},
            )


def _managed_tool_citations(tool_name: str, result: str) -> list[dict]:
    """Lift canonical managed search/fetch source metadata out of untrusted tool text."""
    if tool_name not in {"managed_web_search", "managed_web_fetch"}:
        return []
    try:
        payload = json.loads(result)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    entries = payload.get("sources") if tool_name == "managed_web_search" else [payload]
    citations: list[dict] = []
    if not isinstance(entries, list):
        return citations
    for entry in entries:
        if not isinstance(entry, dict) or not _is_http_url(entry.get("url")):
            continue
        title = entry.get("title")
        snippet = entry.get("snippet")
        if tool_name == "managed_web_fetch":
            snippet = entry.get("text")
        citations.append(
            {
                "source_kind": "web",
                "url": entry["url"],
                "title": title if isinstance(title, str) else None,
                "snippet": snippet[:_CITATION_SNIPPET_CAP] if isinstance(snippet, str) else None,
            }
        )
    return citations


def _usage_pt_ct(usage) -> tuple[int, int] | None:
    if usage is None:
        return None
    pt = getattr(usage, "prompt_tokens", None)
    if pt is None and isinstance(usage, dict):
        pt = usage.get("prompt_tokens")
    ct = getattr(usage, "completion_tokens", None)
    if ct is None and isinstance(usage, dict):
        ct = usage.get("completion_tokens")
    if pt is None or ct is None:
        return None
    try:
        return int(pt), int(ct)
    except (TypeError, ValueError):
        return None


def _assistant_tool_calls_msg(content: str, tool_calls: list[dict]) -> dict:
    return {
        "role": "assistant",
        "content": content or None,
        "tool_calls": [
            {
                "id": tc.get("id") or tc["name"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc.get("args") or "{}"},
            }
            for tc in tool_calls
        ],
    }


def _build_graph(params: dict, ctx: ToolContext):
    """Execute one provider call or tool batch per resumable LangGraph node."""
    hooks = params.get("execution_hooks")

    async def boundary(name: str, **payload: Any) -> Any | None:
        callback = getattr(hooks, name, None) if hooks is not None else None
        if callback is not None:
            return await callback(**payload)
        return None

    async def call_model(state: ChatState) -> dict:
        writer = get_stream_writer()
        messages = list(state["messages"])
        schemas = await tool_runtime.context_tool_schemas(ctx)
        reasoning_effort = None if params["model"] in _REASONING_UNSUPPORTED else params.get("reasoning_effort")
        disable_reasoning_for_tools = bool(schemas) and params["model"] in _TOOL_REASONING_EXPLICIT_NONE
        attempt = 0
        round_index = int(state.get("loop_count", 0))

        async def open_stream(effort, *, disable_reasoning: bool = False):
            nonlocal attempt
            attempt += 1
            replay_payload = await boundary("provider_started", round_index=round_index, attempt=attempt)
            if _abort_code(replay_payload) is not None:
                raise _BoundaryAbort(_abort_code(replay_payload))
            if isinstance(replay_payload, dict):
                return None, replay_payload
            try:
                provider_extra = {"reasoning_effort": "none"} if disable_reasoning else {}
                if params.get("response_format") is not None:
                    provider_extra["response_format"] = params["response_format"]
                return (
                    await litellm_client.acompletion_stream(
                        model=params["model"],
                        messages=messages,
                        tools=schemas,
                        custom_llm_provider=params.get("custom_llm_provider"),
                        api_base=params.get("api_base"),
                        api_key=params.get("api_key"),
                        max_tokens=params.get("max_tokens"),
                        temperature=params.get("temperature"),
                        reasoning_effort=effort,
                        extra=provider_extra or None,
                    ),
                    None,
                )
            except BaseException:
                failure = await boundary("provider_failed", round_index=round_index, attempt=attempt)
                if _abort_code(failure) is not None:
                    raise _BoundaryAbort(_abort_code(failure))
                raise

        try:
            response, replay_payload = await open_stream(
                None if disable_reasoning_for_tools else reasoning_effort,
                disable_reasoning=disable_reasoning_for_tools,
            )
        except _BoundaryAbort as exc:
            writer(
                {
                    "type": "error",
                    "code": str(exc),
                    "message": "이전 모델 호출 결과를 안전하게 확인할 수 없습니다",
                }
            )
            return {"model_failed": True, "pending_tool_calls": []}
        except Exception as exc:
            if schemas and _is_tool_reasoning_conflict(exc):
                logger.warning("tool 요청의 기본 reasoning을 명시적으로 비활성화해 재시도 model=%s", params["model"])
                try:
                    response, replay_payload = await open_stream(None, disable_reasoning=True)
                except Exception:
                    logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                    writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                    return {"model_failed": True, "pending_tool_calls": []}
                _TOOL_REASONING_EXPLICIT_NONE.add(params["model"])
            elif reasoning_effort:
                logger.warning(
                    "reasoning 포함 요청 실패 — reasoning 없이 재시도 model=%s", params.get("model"), exc_info=True
                )
                try:
                    response, replay_payload = await open_stream(None)
                except Exception:
                    logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                    writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                    return {"model_failed": True, "pending_tool_calls": []}
                _REASONING_UNSUPPORTED.add(params["model"])
            else:
                logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                return {"model_failed": True, "pending_tool_calls": []}

        citations_by_url = {item["url"]: item for item in state.get("citations", []) if item.get("url")}
        if replay_payload is not None:
            response_text = str(replay_payload.get("text", ""))
            replay_calls = replay_payload.get("tool_calls", [])
            tool_calls = [item for item in replay_calls if isinstance(item, dict) and item.get("name")]
            for citation in replay_payload.get("citations", []):
                if isinstance(citation, dict) and citation.get("url"):
                    citations_by_url[citation["url"]] = citation
            replay_reasoning = str(replay_payload.get("reasoning", ""))
            if replay_reasoning:
                reasoning_event: dict[str, Any] = {"type": "reasoning", "text": replay_reasoning}
                if replay_payload.get("_durable_replay") is True:
                    reasoning_event["_durable_replay"] = True
                writer(reasoning_event)
            if response_text:
                token_event: dict[str, Any] = {"type": "token", "text": response_text}
                if replay_payload.get("_durable_replay") is True:
                    token_event["_durable_replay"] = True
                writer(token_event)
            replay_usage = replay_payload.get("usage", {})
            round_usage = (
                max(0, int(replay_usage.get("prompt_tokens", 0))),
                max(0, int(replay_usage.get("completion_tokens", 0))),
            )
        else:
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            tool_acc: dict[int, dict] = {}
            final_usage = None
            try:
                async for chunk in response:
                    delta = _delta(chunk)
                    if delta is not None:
                        reasoning = _delta_reasoning(delta)
                        if reasoning:
                            reasoning_parts.append(reasoning)
                            writer({"type": "reasoning", "text": reasoning})
                        content = _delta_content(delta)
                        if content:
                            text_parts.append(content)
                            writer({"type": "token", "text": content})
                        _accumulate_tool_calls(delta, tool_acc)
                    _extract_citations(chunk, delta, citations_by_url)
                    usage = _get(chunk, "usage")
                    if usage is not None:
                        final_usage = usage
            except Exception:
                failure = await boundary("provider_failed", round_index=round_index, attempt=attempt)
                if _abort_code(failure) is not None:
                    writer(
                        {
                            "type": "error",
                            "code": _abort_code(failure),
                            "message": "이전 모델 호출 결과를 안전하게 확인할 수 없습니다",
                        }
                    )
                    return {"model_failed": True, "pending_tool_calls": []}
                logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                return {"model_failed": True, "pending_tool_calls": []}
            tool_calls = [tool_call for tool_call in tool_acc.values() if tool_call.get("name")]
            round_usage = _usage_pt_ct(final_usage)
            if round_usage is None:
                tool_payload = json.dumps(tool_calls, ensure_ascii=False, sort_keys=True) if tool_calls else ""
                round_usage = litellm_client.extract_usage(
                    params["model"], messages, "".join(text_parts) + tool_payload, None
                )
            response_text = "".join(text_parts)
            await boundary(
                "provider_completed",
                round_index=round_index,
                attempt=attempt,
                usage={"prompt_tokens": round_usage[0], "completion_tokens": round_usage[1]},
                result_payload={
                    "text": response_text,
                    "reasoning": "".join(reasoning_parts),
                    "tool_calls": tool_calls,
                    "citations": list(citations_by_url.values()),
                    "usage": {"prompt_tokens": round_usage[0], "completion_tokens": round_usage[1]},
                },
            )

        previous_usage = state.get("usage", {})
        total_usage = {
            "prompt_tokens": int(previous_usage.get("prompt_tokens", 0)) + round_usage[0],
            "completion_tokens": int(previous_usage.get("completion_tokens", 0)) + round_usage[1],
        }
        next_messages = messages
        if tool_calls:
            next_messages = messages + [_assistant_tool_calls_msg(response_text, tool_calls)]
        return {
            "messages": next_messages,
            "pending_tool_calls": tool_calls,
            "final_text": response_text,
            "citations": list(citations_by_url.values()),
            "usage": total_usage,
            "model_failed": False,
        }

    async def route_tools(_state: ChatState) -> dict:
        return {}

    def next_step(state: ChatState) -> str:
        if state.get("model_failed"):
            return "finalize"
        if state.get("pending_tool_calls") and state.get("loop_count", 0) < _MAX_TOOL_STEPS:
            return "execute_tools"
        return "finalize"

    async def execute_tools(state: ChatState) -> dict:
        writer = get_stream_writer()
        messages = list(state["messages"])
        tool_calls = state.get("pending_tool_calls", [])
        round_index = int(state.get("loop_count", 0))
        tool_messages: list[dict[str, str]] = []
        citations_by_url = {item["url"]: item for item in state.get("citations", []) if item.get("url")}
        journals_tool_events = bool(getattr(hooks, "journals_tool_events", False))
        tool_usage = list(state.get("tool_usage", []))
        writer(
            {
                "type": "assistant_tool_calls",
                "content": state.get("final_text") or None,
                "tool_calls": [
                    {
                        "id": tool_call.get("id") or tool_call["name"],
                        "name": tool_call["name"],
                        "args": tool_call.get("args") or "{}",
                    }
                    for tool_call in tool_calls
                ],
            }
        )
        for tool_index, tool_call in enumerate(tool_calls):
            tool_call_id = tool_call.get("id") or tool_call["name"]
            try:
                arguments = json.loads(tool_call.get("args") or "{}")
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            replay_payload = await boundary(
                "tool_started",
                round_index=round_index,
                tool_index=tool_index,
                tool_call_id=tool_call_id,
                tool_name=tool_call["name"],
                arguments=arguments,
            )
            if _abort_code(replay_payload) is not None:
                raise _BoundaryAbort(_abort_code(replay_payload))
            tool_event = {
                "type": "tool_call",
                "tool_call_id": tool_call_id,
                "name": tool_call["name"],
                "args": tool_call.get("args") or "{}",
            }
            if journals_tool_events:
                tool_event["_durable_journaled"] = True
            writer(tool_event)
            if isinstance(replay_payload, dict):
                replay_content = replay_payload.get("content")
                if not isinstance(replay_content, str):
                    raise RuntimeError("completed tool segment has invalid replay payload")
                result = replay_content
                visible = replay_payload.get("visible") is not False
                execution_usage = replay_payload.get("usage")
                if not isinstance(execution_usage, list):
                    execution_usage = []
                warning_code = None
            else:
                try:
                    execution_result = await tool_runtime.context_execute_result(
                        tool_call["name"],
                        arguments,
                        replace(ctx, advisor_visible_messages=tuple(messages)),
                    )
                    result = execution_result.content
                    visible = execution_result.visible
                    execution_usage = list(execution_result.usage)
                    warning_code = execution_result.warning_code
                except BaseException:
                    await boundary(
                        "tool_failed",
                        round_index=round_index,
                        tool_index=tool_index,
                        tool_call_id=tool_call_id,
                        tool_name=tool_call["name"],
                    )
                    raise
                await boundary(
                    "tool_completed",
                    round_index=round_index,
                    tool_index=tool_index,
                    tool_call_id=tool_call_id,
                    tool_name=tool_call["name"],
                    result_payload={
                        "content": result,
                        "tool_name": tool_call["name"],
                        "usage": execution_usage,
                        "visible": visible,
                        "warning_code": warning_code,
                    },
                )
            if warning_code:
                writer({"type": "warning", "code": warning_code, "safe_message": "Advisor request failed."})
            tool_result_event = {
                "type": "tool_result",
                "tool_call_id": tool_call_id,
                "name": tool_call["name"],
                "content": result if visible else "",
                "hidden": not visible,
            }
            if journals_tool_events:
                tool_result_event["_durable_journaled"] = True
            writer(tool_result_event)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_call["name"],
                    "content": result,
                }
            )
            tool_usage.extend(item for item in execution_usage if isinstance(item, dict))
            if visible:
                for citation in _managed_tool_citations(tool_call["name"], result):
                    citations_by_url[citation["url"]] = citation
        return {
            "messages": messages + tool_messages,
            "pending_tool_calls": [],
            "loop_count": state.get("loop_count", 0) + 1,
            "citations": list(citations_by_url.values()),
            "tool_usage": tool_usage,
        }

    async def finalize(state: ChatState) -> dict:
        if state.get("model_failed"):
            return {"messages": state["messages"]}
        writer = get_stream_writer()
        if state.get("citations"):
            writer({"type": "citations", "items": state["citations"]})
        usage_event = {"type": "usage", "usage": state.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})}
        if state.get("tool_usage"):
            usage_event["tool_usage"] = state["tool_usage"]
        writer(usage_event)
        return {"messages": state["messages"] + [{"role": "assistant", "content": state.get("final_text", "")}]}

    builder = StateGraph(ChatState)
    builder.add_node("call_model", call_model)
    builder.add_node("route_tools", route_tools)
    builder.add_node("execute_tools", execute_tools)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", "route_tools")
    builder.add_conditional_edges("route_tools", next_step, {"execute_tools": "execute_tools", "finalize": "finalize"})
    builder.add_edge("execute_tools", "call_model")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=chat_checkpointer.saver)


async def stream(
    *,
    model: str,
    messages: list[dict],
    project_id: str,
    user_id: str,
    custom_llm_provider: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    selected_tool_ids: tuple[int, ...] | None = None,
    selected_mcp_ids: tuple[int, ...] | None = None,
    tools_enabled: bool = True,
    managed_search: dict[str, Any] | None = None,
    managed_fetch: dict[str, Any] | None = None,
    managed_advisor: dict[str, Any] | None = None,
    response_format: dict[str, Any] | None = None,
    execution_hooks: object | None = None,
    run_id: str | None = None,
) -> AsyncIterator[dict]:
    """Stream chat events while awaiting durable execution-boundary hooks."""
    params = {
        "model": model,
        "custom_llm_provider": custom_llm_provider,
        "api_base": api_base,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning_effort": reasoning_effort,
        "execution_hooks": execution_hooks,
        "response_format": response_format,
    }
    ctx = ToolContext(
        project_id=project_id,
        user_id=user_id,
        selected_tool_ids=selected_tool_ids,
        tools_enabled=tools_enabled,
        selected_mcp_ids=selected_mcp_ids,
        execution_hooks=execution_hooks,
        managed_search=managed_search,
        managed_fetch=managed_fetch,
        managed_advisor=managed_advisor,
    )
    graph = _build_graph(params, ctx)
    config = {"configurable": {"thread_id": run_id}} if run_id else None
    async for chunk in graph.astream({"messages": messages}, config=config, stream_mode="custom"):
        yield chunk
