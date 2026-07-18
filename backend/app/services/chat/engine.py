"""chat_engine 인터페이스 — completions 엔드포인트가 의존하는 스트리밍 경계.

Phase 2: 실제 구현을 LangGraph 에이전트 그래프(graph.stream)에 위임한다. 이벤트 계약
(token/tool_call/usage/error)은 불변이므로 엔드포인트·테스트는 engine.stream 을 그대로 호출/패치한다.
project_id/user_id 는 툴 실행의 테넌트 컨텍스트로 전달된다(LLM 입력 아님).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.services.chat import graph


async def stream(
    *,
    model: str,
    messages: list[dict],
    project_id: str,
    user_id: str,
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[dict]:
    async for ev in graph.stream(
        model=model,
        messages=messages,
        project_id=project_id,
        user_id=user_id,
        api_base=api_base,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    ):
        yield ev
