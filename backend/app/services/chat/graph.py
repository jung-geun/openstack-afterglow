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
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.services.chat import litellm_client, tool_runtime
from app.services.chat.tools import ToolContext

logger = logging.getLogger(__name__)

_MAX_TOOL_STEPS = 4  # 툴 실행 라운드 상한(무한 루프 방지) — 초과 시 마지막 턴을 최종 답변으로


class ChatState(TypedDict):
    messages: list[dict]


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


def _usage_pt_ct(usage) -> tuple[int, int]:
    if usage is None:
        return 0, 0
    pt = getattr(usage, "prompt_tokens", None)
    if pt is None and isinstance(usage, dict):
        pt = usage.get("prompt_tokens")
    ct = getattr(usage, "completion_tokens", None)
    if ct is None and isinstance(usage, dict):
        ct = usage.get("completion_tokens")
    try:
        return int(pt or 0), int(ct or 0)
    except (TypeError, ValueError):
        return 0, 0


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
    """요청 파라미터·툴 컨텍스트를 클로저로 캡처한 1-노드 에이전트 그래프."""

    async def agent(state: ChatState) -> dict:
        writer = get_stream_writer()
        msgs = list(state["messages"])
        schemas = await tool_runtime.context_tool_schemas(ctx)  # 내장 + 동적 커스텀 툴
        total_pt = total_ct = 0
        final_text = ""

        for step in range(_MAX_TOOL_STEPS + 1):
            text_parts: list[str] = []
            tool_acc: dict[int, dict] = {}
            final_usage = None
            try:
                resp = await litellm_client.acompletion_stream(
                    model=params["model"],
                    messages=msgs,
                    tools=schemas,
                    custom_llm_provider=params.get("custom_llm_provider"),
                    api_base=params.get("api_base"),
                    api_key=params.get("api_key"),
                    max_tokens=params.get("max_tokens"),
                    temperature=params.get("temperature"),
                )
                async for chunk in resp:
                    delta = _delta(chunk)
                    if delta is not None:
                        content = _delta_content(delta)
                        if content:
                            text_parts.append(content)
                            writer({"type": "token", "text": content})
                        _accumulate_tool_calls(delta, tool_acc)
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        final_usage = usage
            except Exception:
                logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                return {"messages": msgs}

            pt, ct = _usage_pt_ct(final_usage)
            total_pt += pt
            total_ct += ct

            tool_calls = [tc for tc in tool_acc.values() if tc.get("name")]
            if tool_calls and step < _MAX_TOOL_STEPS:
                msgs.append(_assistant_tool_calls_msg("".join(text_parts), tool_calls))
                for tc in tool_calls:
                    writer({"type": "tool_call", "name": tc["name"]})
                    try:
                        args = json.loads(tc.get("args") or "{}")
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    result = await tool_runtime.context_execute(tc["name"], args, ctx)
                    msgs.append({"role": "tool", "tool_call_id": tc.get("id") or tc["name"], "content": result})
                continue  # 다음 턴(툴 결과 반영)

            final_text = "".join(text_parts)
            break

        writer({"type": "usage", "usage": {"prompt_tokens": total_pt, "completion_tokens": total_ct}})
        return {"messages": msgs + [{"role": "assistant", "content": final_text}]}

    builder = StateGraph(ChatState)
    builder.add_node("agent", agent)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile()


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
) -> AsyncIterator[dict]:
    """engine.stream 과 동일 계약. LangGraph custom 스트림으로 token/tool_call/usage/error yield.

    project_id/user_id 는 툴 실행의 테넌트 컨텍스트(ToolContext)로만 쓰인다(LLM 입력 아님).
    """
    params = {
        "model": model,
        "custom_llm_provider": custom_llm_provider,
        "api_base": api_base,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    ctx = ToolContext(project_id=project_id, user_id=user_id)
    graph = _build_graph(params, ctx)
    async for chunk in graph.astream({"messages": messages}, stream_mode="custom"):
        yield chunk
