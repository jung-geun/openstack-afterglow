"""chat_engine 인터페이스 — completions 엔드포인트가 의존하는 스트리밍 경계.

Phase 2: 실제 구현을 LangGraph 그래프(graph.stream)에 위임한다. 이벤트 계약(token/usage/error)은
불변이므로 엔드포인트·테스트는 engine.stream 을 그대로 호출/패치한다.
(Phase 1 의 litellm 직접 구현은 graph.py 로 이관됨.)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.services.chat import graph


async def stream(
    *,
    model: str,
    messages: list[dict],
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[dict]:
    async for ev in graph.stream(
        model=model,
        messages=messages,
        api_base=api_base,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    ):
        yield ev
