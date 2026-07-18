"""litellm 호출 래퍼 + 비용/토큰 계산.

핵심 책임:
- provider 설정(api_base/api_key)을 주입해 litellm 를 호출(스트리밍/비스트리밍).
- ⚠️ 스트리밍 응답은 기본적으로 usage 를 주지 않으므로 `stream_options={"include_usage": True}`
  로 요청하고, 그래도 없으면 `litellm.token_counter` 로 폴백 산출한다(과금 0원 방지).
- 토큰 수 → USD 비용 산출(litellm 내장 가격표, `cost_per_token`).

litellm 은 무거운 import 라 모든 함수 내부에서 lazy import 한다(startup 속도 유지).
litellm 의 로컬 계산(token_counter/cost_per_token)만 쓰는 함수는 네트워크가 필요 없다.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


def count_tokens(model: str, *, messages: list[dict] | None = None, text: str | None = None) -> int:
    """litellm.token_counter 로 토큰 수 산출. 실패 시 대략치(4 chars ≈ 1 token) 폴백."""
    try:
        import litellm

        if messages is not None:
            return int(litellm.token_counter(model=model, messages=messages))
        return int(litellm.token_counter(model=model, text=text or ""))
    except Exception:
        logger.warning("litellm token_counter 실패 model=%s — 대략치 폴백", model, exc_info=True)
        raw = text if text is not None else "".join(str(m.get("content", "")) for m in (messages or []))
        return max(1, len(raw) // 4)


def _usage_field(usage: Any, key: str) -> int | None:
    """usage(dict 또는 litellm Usage 객체)에서 정수 필드를 안전하게 추출."""
    val = usage.get(key) if isinstance(usage, Mapping) else getattr(usage, key, None)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def extract_usage(
    model: str,
    messages: list[dict],
    completion_text: str,
    final_usage: Any | None,
) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) 산출.

    스트리밍 마지막 청크의 usage 가 있으면 그대로, 없으면 token_counter 폴백.
    이 폴백이 없으면 스트리밍 경로에서 completion_cost 가 0이 되어 과금이 누락된다.
    """
    if final_usage is not None:
        pt = _usage_field(final_usage, "prompt_tokens")
        ct = _usage_field(final_usage, "completion_tokens")
        if pt is not None and ct is not None:
            return pt, ct

    prompt_tokens = count_tokens(model, messages=messages)
    completion_tokens = count_tokens(model, text=completion_text)
    return prompt_tokens, completion_tokens


def cost_from_usage(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """토큰 수 → USD 비용(litellm 내장 가격표). 산출 실패 시 0.0(로그).

    반환값은 raw_cost(USD). 크레딧 환산·마진은 credit 레이어에서 처리한다.
    """
    try:
        import litellm

        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return float(prompt_cost) + float(completion_cost)
    except Exception:
        logger.warning("litellm cost_per_token 실패 model=%s — raw_cost=0", model, exc_info=True)
        return 0.0


def _build_params(
    model: str,
    messages: list[dict],
    *,
    api_base: str | None,
    api_key: str | None,
    max_tokens: int | None,
    temperature: float | None,
    tools: list[dict] | None = None,
    extra: dict | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"model": model, "messages": messages}
    if api_base:
        params["api_base"] = api_base
    if api_key:
        params["api_key"] = api_key
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    if temperature is not None:
        params["temperature"] = temperature
    if tools:
        params["tools"] = tools
    if extra:
        params.update(extra)
    return params


async def acompletion(
    model: str,
    messages: list[dict],
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    tools: list[dict] | None = None,
    extra: dict | None = None,
) -> Any:
    """비스트리밍 litellm 호출."""
    import litellm

    params = _build_params(
        model,
        messages,
        api_base=api_base,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        tools=tools,
        extra=extra,
    )
    return await litellm.acompletion(**params)


async def acompletion_stream(
    model: str,
    messages: list[dict],
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    tools: list[dict] | None = None,
    extra: dict | None = None,
) -> Any:
    """스트리밍 litellm 호출. usage 계측을 위해 include_usage 를 강제한다.

    반환값은 async iterator(청크). 호출부가 청크 델타를 SSE 로 전달하고,
    마지막 usage 청크를 extract_usage 에 넘겨 과금한다. tools 지정 시 tool_call 델타도 스트리밍된다.
    """
    import litellm

    params = _build_params(
        model,
        messages,
        api_base=api_base,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        tools=tools,
        extra=extra,
    )
    params["stream"] = True
    params["stream_options"] = {"include_usage": True}
    return await litellm.acompletion(**params)
