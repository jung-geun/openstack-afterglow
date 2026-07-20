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

# reasoning 파라미터를 거부한 모델 캐시(프로세스 수명). supports_reasoning 이 True 여도 litellm/provider
# 매핑 불일치로 400 이 나는 모델(예: 일부 Claude 의 thinking.type)을 기억해 매 요청 실패를 반복하지 않는다.
_REASONING_UNSUPPORTED: set[str] = set()


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
    """청크/델타에서 출처를 정규화해 acc(url→{url,title,snippet})에 누적. provider 무관.

    - Perplexity: 청크 최상위 `search_results`(풍부: title/url/snippet) + `citations`(url 목록).
    - Gemini grounding / OpenAI web search: `delta.annotations`[{type:url_citation, url_citation:{url,title}}].
    """
    # search_results — 풍부한 소스는 덮어써서 우선 반영
    for item in _get(chunk, "search_results") or []:
        url = _get(item, "url")
        if not _is_http_url(url):
            continue
        snippet = _get(item, "snippet")
        acc[url] = {
            "url": url,
            "title": _get(item, "title"),
            "snippet": (snippet[:_CITATION_SNIPPET_CAP] if isinstance(snippet, str) else None),
        }
    # citations — url 만 있는 목록(이미 풍부 항목이 있으면 유지)
    for c in _get(chunk, "citations") or []:
        if _is_http_url(c):
            acc.setdefault(c, {"url": c, "title": None, "snippet": None})
    # annotations(url_citation) — Gemini/OpenAI
    for a in _get(delta, "annotations") or []:
        uc = _get(a, "url_citation") or {}
        url = _get(uc, "url")
        if _is_http_url(url):
            acc.setdefault(url, {"url": url, "title": _get(uc, "title"), "snippet": None})


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
    """요청 파라미터·툴 컨텍스트를 클로저로 캡처한 1-노드 에이전트 그래프."""

    async def agent(state: ChatState) -> dict:
        writer = get_stream_writer()
        msgs = list(state["messages"])
        schemas = await tool_runtime.context_tool_schemas(ctx)  # 내장 + 동적 커스텀 툴
        total_pt = total_ct = 0
        final_text = ""
        citations_acc: dict[str, dict] = {}  # url→소스, 전체 스텝 누적
        # reasoning 은 best-effort: litellm/provider 가 파라미터를 거부하면(예: 일부 Claude 모델의
        # thinking.type 불일치로 400) reasoning 없이 재시도해 채팅이 깨지지 않게 한다. 실패 후엔 이후 스텝도 생략.
        # 이미 거부 이력이 있는 모델은 처음부터 reasoning 을 붙이지 않는다(실패 요청 반복 방지).
        reasoning_effort = None if params["model"] in _REASONING_UNSUPPORTED else params.get("reasoning_effort")

        async def _open(effort):
            return await litellm_client.acompletion_stream(
                model=params["model"],
                messages=msgs,
                tools=schemas,
                custom_llm_provider=params.get("custom_llm_provider"),
                api_base=params.get("api_base"),
                api_key=params.get("api_key"),
                max_tokens=params.get("max_tokens"),
                temperature=params.get("temperature"),
                reasoning_effort=effort,
            )

        for step in range(_MAX_TOOL_STEPS + 1):
            text_parts: list[str] = []
            tool_acc: dict[int, dict] = {}
            final_usage = None
            # 스트림 열기(연결·초기 요청). reasoning 파라미터가 원인인 400 은 여기서 발생하므로 재시도로 흡수.
            try:
                resp = await _open(reasoning_effort)
            except Exception:
                if reasoning_effort:
                    logger.warning(
                        "reasoning 포함 요청 실패 — reasoning 없이 재시도 model=%s", params.get("model"), exc_info=True
                    )
                    reasoning_effort = None  # 이후 스텝도 reasoning 생략(반복 실패 방지)
                    try:
                        resp = await _open(None)
                    except Exception:
                        logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                        writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                        return {"messages": msgs}
                    # reasoning 없이 성공 → 원인은 reasoning 파라미터. 이 모델은 이후 요청에서 처음부터 생략.
                    _REASONING_UNSUPPORTED.add(params["model"])
                else:
                    logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                    writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                    return {"messages": msgs}
            try:
                async for chunk in resp:
                    delta = _delta(chunk)
                    if delta is not None:
                        reasoning = _delta_reasoning(delta)
                        if reasoning:
                            # 추론(thinking) 델타 — 최종 답변 텍스트와 별개, 저장하지 않고 라이브 노출.
                            writer({"type": "reasoning", "text": reasoning})
                        content = _delta_content(delta)
                        if content:
                            text_parts.append(content)
                            writer({"type": "token", "text": content})
                        _accumulate_tool_calls(delta, tool_acc)
                    _extract_citations(chunk, delta, citations_acc)
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        final_usage = usage
            except Exception:
                logger.warning("litellm 스트리밍 오류 model=%s", params.get("model"), exc_info=True)
                writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
                return {"messages": msgs}

            tool_calls = [tc for tc in tool_acc.values() if tc.get("name")]
            round_usage = _usage_pt_ct(final_usage)
            if round_usage is None:
                tool_payload = json.dumps(tool_calls, ensure_ascii=False, sort_keys=True) if tool_calls else ""
                round_usage = litellm_client.extract_usage(
                    params["model"],
                    msgs,
                    "".join(text_parts) + tool_payload,
                    None,
                )
            total_pt += round_usage[0]
            total_ct += round_usage[1]
            if tool_calls and step < _MAX_TOOL_STEPS:
                step_text = "".join(text_parts)
                msgs.append(_assistant_tool_calls_msg(step_text, tool_calls))
                # 저장용 이벤트 — completions 가 chat_messages(암호화)에 assistant tool_calls 기록.
                writer(
                    {
                        "type": "assistant_tool_calls",
                        "content": step_text or None,
                        "tool_calls": [
                            {"id": tc.get("id") or tc["name"], "name": tc["name"], "args": tc.get("args") or "{}"}
                            for tc in tool_calls
                        ],
                    }
                )
                for tc in tool_calls:
                    writer({"type": "tool_call", "name": tc["name"]})  # 진행 표시(SSE 중계)
                    try:
                        args = json.loads(tc.get("args") or "{}")
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    result = await tool_runtime.context_execute(tc["name"], args, ctx)
                    tc_id = tc.get("id") or tc["name"]
                    msgs.append({"role": "tool", "tool_call_id": tc_id, "content": result})
                    # 저장용 이벤트 — completions 가 role=tool 결과를 암호화 기록.
                    writer({"type": "tool_result", "tool_call_id": tc_id, "name": tc["name"], "content": result})
                continue  # 다음 턴(툴 결과 반영)

            final_text = "".join(text_parts)
            break

        if citations_acc:
            # 출처 — completions 가 최종 답변에 저장 + SSE 중계. 최종 답변 직전 emit.
            writer({"type": "citations", "items": list(citations_acc.values())})
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
    reasoning_effort: str | None = None,
) -> AsyncIterator[dict]:
    """engine.stream 과 동일 계약. LangGraph custom 스트림으로 token/reasoning/tool_call/usage/error yield.

    project_id/user_id 는 툴 실행의 테넌트 컨텍스트(ToolContext)로만 쓰인다(LLM 입력 아님).
    reasoning_effort 는 지원 모델에만 적용돼 추론(reasoning) 이벤트를 유발한다.
    """
    params = {
        "model": model,
        "custom_llm_provider": custom_llm_provider,
        "api_base": api_base,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning_effort": reasoning_effort,
    }
    ctx = ToolContext(project_id=project_id, user_id=user_id)
    graph = _build_graph(params, ctx)
    async for chunk in graph.astream({"messages": messages}, stream_mode="custom"):
        yield chunk
