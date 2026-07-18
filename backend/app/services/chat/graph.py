"""Phase 2 chat_engine — LangGraph StateGraph 로 litellm 호출을 감싼다(MCP·체크포인터 미포함).

설계 결정(2026-07-18):
- litellm_client 를 그대로 쓰고(ChatLiteLLM/langchain-community 미도입), LangGraph 는 그래프 구조·
  상태·스트리밍만 담당한다. litellm 은 LangChain 챗모델이 아니므로 stream_mode="messages" 대신
  **stream_mode="custom" + writer(StreamWriter)** 로 토큰 델타를 emit 한다.
- 대화 전사는 MySQL chat_messages(source of truth)에서 매 요청 로드해 messages 로 주입하므로,
  체크포인터 없이도 대화 연속성이 동작한다(Postgres 체크포인터는 후속 resume/durable-state 강화).
- 이벤트 계약은 Phase 1 engine.py 와 동일: token / usage / error → completions 엔드포인트 불변.
- MCP 툴 노드·조건부 엣지(tools_condition)는 이 구조(START→agent→END)에 후속 슬라이스에서 추가.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.services.chat import litellm_client

logger = logging.getLogger(__name__)


class ChatState(TypedDict):
    messages: list[dict]


def _chunk_text(chunk) -> str | None:
    """litellm 스트리밍 청크(OpenAI 형식)에서 delta.content 를 방어적으로 추출."""
    try:
        choices = getattr(chunk, "choices", None)
        if choices is None and isinstance(chunk, dict):
            choices = chunk.get("choices")
        if not choices:
            return None
        first = choices[0]
        delta = getattr(first, "delta", None)
        if delta is None and isinstance(first, dict):
            delta = first.get("delta")
        if delta is None:
            return None
        content = getattr(delta, "content", None)
        if content is None and isinstance(delta, dict):
            content = delta.get("content")
        return content
    except Exception:
        return None


def _build_graph(params: dict):
    """요청 파라미터(model/api_base/...)를 클로저로 캡처한 1-노드 그래프를 컴파일.

    1-노드 컴파일은 저렴하고, config 배관 없이 노드가 파라미터를 직접 참조한다.
    """

    async def agent(state: ChatState) -> dict:
        writer = get_stream_writer()
        messages = state["messages"]
        parts: list[str] = []
        final_usage = None
        try:
            resp = await litellm_client.acompletion_stream(
                model=params["model"],
                messages=messages,
                api_base=params.get("api_base"),
                api_key=params.get("api_key"),
                max_tokens=params.get("max_tokens"),
                temperature=params.get("temperature"),
            )
        except Exception:
            logger.warning("litellm 스트리밍 시작 실패 model=%s", params.get("model"), exc_info=True)
            writer({"type": "error", "message": "모델 호출을 시작할 수 없습니다"})
            return {"messages": messages}

        try:
            async for chunk in resp:
                text = _chunk_text(chunk)
                if text:
                    parts.append(text)
                    writer({"type": "token", "text": text})
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    final_usage = usage
        except Exception:
            logger.warning("litellm 스트리밍 중 오류 model=%s", params.get("model"), exc_info=True)
            writer({"type": "error", "message": "모델 응답 중 오류가 발생했습니다"})
            return {"messages": messages}

        writer({"type": "usage", "usage": final_usage})
        return {"messages": messages + [{"role": "assistant", "content": "".join(parts)}]}

    builder = StateGraph(ChatState)
    builder.add_node("agent", agent)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    return builder.compile()


async def stream(
    *,
    model: str,
    messages: list[dict],
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[dict]:
    """engine.stream 과 동일 계약. LangGraph custom 스트림으로 token/usage/error 이벤트를 yield."""
    params = {
        "model": model,
        "api_base": api_base,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    graph = _build_graph(params)
    async for chunk in graph.astream({"messages": messages}, stream_mode="custom"):
        # chunk 은 노드가 writer(...)로 emit 한 dict 그대로
        yield chunk
