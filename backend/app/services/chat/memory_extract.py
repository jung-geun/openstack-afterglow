"""채팅 완료 후 사용자 메모리 자동 추출 — 관리자 지정 초소형 모델(is_memory_model)로

기존 메모리와 최근 대화를 비교해 **추가/갱신할 델타만** 구조화 op 로 뽑아 반영한다.

⚠️ 델타 계약(중복 무한 증식 방지): 모델에 기존 메모리를 **id 와 함께** 주고
`{"op":"add","content":...}` / `{"op":"update","id":N,"content":...}` 만 출력하게 한다.
- add: 새 사실. update: 기존 사실 갱신. 없으면 빈 배열.
- 방어적 JSON 파싱 — 형식 위반/오류는 조용히 무시(부가 기능이라 대화를 막지 않음).

⚠️ 비용은 시스템 부담(title_summary 와 동일: source="system", charge_wallet=False).
⚠️ 프라이버시: 복호화된 기존 메모리 + 최근 대화가 (외부 프로바이더일 수 있는) 초소형 모델로 전송된다.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Mapping

from app.services.chat import conversation_store as cs
from app.services.chat import credit, litellm_client
from app.services.chat import memory_store as ms
from app.services.chat import provider_store as ps

logger = logging.getLogger(__name__)

_MAX_TOKENS = 400
_MAX_EXISTING = 30  # 프롬프트에 넣는 기존 메모리 상한(비용)
_MAX_OPS = 6  # 한 번에 반영할 op 상한(runaway 방지)
_MAX_CONTENT_CHARS = 2000
_SYSTEM = (
    "당신은 사용자에 대해 장기 기억할 사실을 관리한다. 아래 [기존 메모리]와 [최근 대화]를 보고 "
    "추가하거나 갱신할 항목만 JSON 배열로 출력하라. 각 항목은 다음 둘 중 하나다:\n"
    '- {"op":"add","content":"새로 기억할 한 문장"}\n'
    '- {"op":"update","id":<기존 메모리 id>,"content":"갱신된 한 문장"}\n'
    "규칙: 이미 있는 사실은 중복 추가하지 말고 필요 시 update 하라. 일시적·사소한 내용은 제외하고 "
    "안정적인 선호·사실만 기록하라. content 는 한 문장이며 사용자의 언어를 따른다. "
    "새로 기억하거나 갱신할 것이 없으면 빈 배열 []를 출력하라. JSON 배열만 출력하고 설명은 하지 마라."
)


def _resp_text(resp) -> str:
    try:
        choices = getattr(resp, "choices", None)
        if choices is None and isinstance(resp, Mapping):
            choices = resp.get("choices")
        first = choices[0]
        msg = getattr(first, "message", None)
        if msg is None and isinstance(first, Mapping):
            msg = first.get("message")
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, Mapping):
            content = msg.get("content")
        return content or ""
    except Exception:
        return ""


def _parse_ops(text: str) -> list[dict]:
    """모델 출력에서 JSON 배열을 방어적으로 추출·파싱. 실패 시 빈 목록."""
    if not text:
        return []
    # ```json ... ``` 펜스나 잡음 제거 — 첫 '[' ~ 마지막 ']' 구간만.
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


async def _apply_ops(ops: list[dict], user_id: str, project_id: str, existing_ids: set[int]) -> None:
    for op in ops[:_MAX_OPS]:
        if not isinstance(op, dict):
            continue
        kind = op.get("op")
        content = op.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        content = content.strip()[:_MAX_CONTENT_CHARS]
        try:
            if kind == "add":
                await ms.create_memory(
                    user_id=user_id,
                    project_id=project_id,
                    scope="project",
                    content=content,
                )
            elif kind == "update":
                mid = op.get("id")
                if isinstance(mid, int) and mid in existing_ids:
                    await ms.update_memory(mid, user_id=user_id, project_id=project_id, patch={"content": content})
        except Exception:
            logger.warning("메모리 op 반영 실패 user=%s op=%s", user_id, kind, exc_info=True)


async def generate_memory_if_applicable(*, conversation_id: str, project_id: str, user_id: str) -> None:
    """메모리 모델이 지정돼 있으면 최근 대화에서 메모리 델타를 추출·반영(시스템 과금). 실패는 무시."""
    try:
        resolved = await ps.resolve_memory_model()
    except Exception:
        logger.warning("메모리 추출 모델 조회 실패 conv=%s", conversation_id, exc_info=True)
        return
    if resolved is None:
        return  # 메모리 모델 미지정 — 기능 비활성

    try:
        existing = await ms.list_memories(user_id=user_id, project_id=project_id)
        msgs = await cs.list_messages(conversation_id, user_id=user_id, project_id=project_id, limit=8)
    except Exception:
        return
    active = [m for m in existing if m.get("is_active", True)][:_MAX_EXISTING]
    existing_ids = {m["id"] for m in active}
    # Assistant, tool, and fetched web text are not user-authored facts.
    convo = [m for m in msgs if m.get("role") == "user" and m.get("content")]
    if not convo:
        return

    existing_block = "\n".join(f"- (id {m['id']}) {str(m['content'])[:300]}" for m in active) if active else "(없음)"
    convo_block = "\n".join(f"{m['role']}: {str(m['content'])[:500]}" for m in convo[-6:])
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"[기존 메모리]\n{existing_block}\n\n[최근 대화]\n{convo_block}"},
    ]
    model = resolved["model_name"]

    try:
        resp = await litellm_client.acompletion(
            model,
            messages,
            custom_llm_provider=resolved.get("provider_type"),
            api_base=resolved.get("api_base"),
            api_key=resolved.get("api_key"),
            max_tokens=_MAX_TOKENS,
            temperature=0.2,
        )
    except Exception:
        logger.warning("메모리 추출 호출 실패 conv=%s model=%s", conversation_id, model, exc_info=True)
        return

    text = _resp_text(resp)
    ops = _parse_ops(text)
    if ops:
        await _apply_ops(ops, user_id, project_id, existing_ids)

    # 시스템 부담 과금 — 원장만 기록, 사용자 지갑 미차감. event_id 는 실행마다 고유.
    try:
        usage = getattr(resp, "usage", None)
        if usage is None and isinstance(resp, Mapping):
            usage = resp.get("usage")
        pt, ct = litellm_client.extract_usage(model, messages, text, usage)
        usage_cost = litellm_client.cost_from_usage(
            model,
            pt,
            ct,
            input_price_per_token=resolved.get("input_price_per_token"),
            output_price_per_token=resolved.get("output_price_per_token"),
            price_source=resolved.get("price_source"),
            provider_type=resolved.get("provider_type"),
        )
        await credit.apply_usage(
            event_id=f"memory:{conversation_id}:{uuid.uuid4().hex}",
            user_id=user_id,
            project_id=project_id,
            model_name=model,
            provider=resolved.get("provider_name"),
            prompt_tokens=pt,
            completion_tokens=ct,
            usage_cost=usage_cost,
            margin_multiplier=resolved["margin_multiplier"],
            conversation_id=conversation_id,
            source="system",
            charge_wallet=False,
        )
    except Exception:
        logger.warning("메모리 추출 시스템 과금 기록 실패 conv=%s", conversation_id, exc_info=True)
