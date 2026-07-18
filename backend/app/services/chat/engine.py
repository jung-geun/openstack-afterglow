"""Phase 1 chat_engine — litellm 직접 스트리밍.

Phase 2 에서 이 모듈의 stream() 을 LangGraph 구현으로 교체한다(엔드포인트 이벤트 계약은 불변).

이벤트 계약(async generator 가 yield 하는 dict):
  {"type": "token", "text": <델타 문자열>}
  {"type": "usage", "usage": <litellm usage 객체 또는 None>}   # 스트림 종료 시 1회
  {"type": "error", "message": <사용자용 메시지>}
과금(cost)·영속화는 호출부(completions 엔드포인트)가 담당한다.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.services.chat import litellm_client

logger = logging.getLogger(__name__)


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


async def stream(
    *,
    model: str,
    messages: list[dict],
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AsyncIterator[dict]:
    try:
        resp = await litellm_client.acompletion_stream(
            model=model,
            messages=messages,
            api_base=api_base,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception:
        logger.warning("litellm 스트리밍 시작 실패 model=%s", model, exc_info=True)
        yield {"type": "error", "message": "모델 호출을 시작할 수 없습니다"}
        return

    final_usage = None
    try:
        async for chunk in resp:
            text = _chunk_text(chunk)
            if text:
                yield {"type": "token", "text": text}
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                final_usage = usage
    except Exception:
        logger.warning("litellm 스트리밍 중 오류 model=%s", model, exc_info=True)
        yield {"type": "error", "message": "모델 응답 중 오류가 발생했습니다"}
        return

    yield {"type": "usage", "usage": final_usage}
