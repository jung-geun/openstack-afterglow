"""빌트인 AI 채팅 스트리밍 completions (SSE).

흐름: 쿼터 precheck(fail-closed) → 대화 소유권 검증 → resolve_model 화이트리스트 →
engine.stream 델타 SSE 전송 → finally 에서 사용량 과금(중단 시에도) + assistant 메시지 저장.

SSE 이벤트: token(델타) / error / done(usage·credited_cost). Phase 2 에서 tool_call 추가 예정.
⚠️ 과금은 정상 완료·중단 무관하게 정확히 1회(charged 플래그) — BackgroundTasks 가 정상완료에만
도는 함정을 피하기 위해 스트리밍 제너레이터의 finally 에서 처리한다.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_token_info
from app.config import get_settings
from app.services.chat import conversation_store as cs
from app.services.chat import credit, engine, litellm_client
from app.services.chat import provider_store as ps

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_TOKENS_CAP = 4096
_MAX_MESSAGE_CHARS = 32000
_MAX_HISTORY = 40


class CompletionRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_CHARS)
    model: str | None = Field(default=None, max_length=190)
    max_tokens: int | None = Field(default=None, ge=1, le=_MAX_TOKENS_CAP)
    temperature: float | None = Field(default=None, ge=0, le=2)

    model_config = {"protected_namespaces": ()}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _finalize(*, conversation_id, project_id, user_id, model_name, resolved, text, pt, ct, raw_cost):
    """assistant 메시지 저장(있으면) + 사용량 과금. 차감 크레딧 반환."""
    if text:
        try:
            await cs.add_message(conversation_id, role="assistant", content=text, token_prompt=pt, token_completion=ct)
        except Exception:
            logger.warning("assistant 메시지 저장 실패 conv=%s", conversation_id, exc_info=True)
    return await credit.apply_usage(
        user_id=user_id,
        project_id=project_id,
        model_name=model_name,
        provider=resolved.get("provider_name"),
        prompt_tokens=pt,
        completion_tokens=ct,
        raw_cost=raw_cost,
        margin_multiplier=resolved.get("margin_multiplier", 1.0),
        conversation_id=conversation_id,
        source="web",
    )


@router.post("/conversations/{conversation_id}/completions")
async def create_completion(
    conversation_id: str, payload: CompletionRequest, token_info: dict = Depends(get_token_info)
):
    settings = get_settings()
    project_id = token_info["project_id"]
    user_id = token_info["user_id"]

    # 1. 쿼터 선검사 (fail-closed)
    try:
        await credit.precheck(user_id, project_id)
    except credit.QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except credit.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # 2. 대화 소유권
    try:
        conv = await cs.get_conversation(conversation_id, project_id=project_id, user_id=user_id)
    except cs.ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except cs.ConversationForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # 3. 모델 화이트리스트 (활성 카탈로그에 없으면 거부)
    model_name = payload.model or conv.get("model_name") or settings.chat_default_model
    if not model_name:
        raise HTTPException(status_code=400, detail="모델이 지정되지 않았습니다")
    try:
        resolved = await ps.resolve_model(model_name)
    except ps.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if resolved is None:
        raise HTTPException(status_code=400, detail=f"허용되지 않은 모델입니다: {model_name}")

    # 4. 히스토리 로드 + 사용자 메시지 저장
    try:
        history = await cs.list_messages(conversation_id, project_id=project_id, user_id=user_id, limit=_MAX_HISTORY)
        await cs.add_message(conversation_id, role="user", content=payload.message)
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    messages = [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")]
    messages.append({"role": "user", "content": payload.message})
    max_tokens = min(payload.max_tokens or _MAX_TOKENS_CAP, _MAX_TOKENS_CAP)

    async def event_stream():
        parts: list[str] = []
        final_usage = None
        charged = False
        errored = False
        try:
            async for ev in engine.stream(
                model=model_name,
                messages=messages,
                api_base=resolved.get("api_base"),
                api_key=resolved.get("api_key"),
                max_tokens=max_tokens,
                temperature=payload.temperature,
            ):
                etype = ev.get("type")
                if etype == "token":
                    parts.append(ev["text"])
                    yield _sse({"type": "token", "text": ev["text"]})
                elif etype == "usage":
                    final_usage = ev.get("usage")
                elif etype == "error":
                    # 모델 하드 실패 — 과금하지 않고 done 도 보내지 않는다.
                    errored = True
                    yield _sse({"type": "error", "message": ev.get("message", "오류")})

            # 정상 완료(모델 오류 없을 때만) → 사용량 산출·과금·저장·done
            if not errored:
                text = "".join(parts)
                pt, ct = litellm_client.extract_usage(model_name, messages, text, final_usage)
                raw_cost = litellm_client.cost_from_usage(model_name, pt, ct)
                credited = await _finalize(
                    conversation_id=conversation_id,
                    project_id=project_id,
                    user_id=user_id,
                    model_name=model_name,
                    resolved=resolved,
                    text=text,
                    pt=pt,
                    ct=ct,
                    raw_cost=raw_cost,
                )
                charged = True
                yield _sse(
                    {"type": "done", "prompt_tokens": pt, "completion_tokens": ct, "credited_cost": float(credited)}
                )
        finally:
            # 중단(disconnect) 등 비정상 종료 시에도 부분 사용량을 과금(정확히 1회).
            # 단, 모델 하드 실패(errored)면 과금하지 않는다.
            if not charged and not errored and parts:
                text = "".join(parts)
                pt, ct = litellm_client.extract_usage(model_name, messages, text, final_usage)
                raw_cost = litellm_client.cost_from_usage(model_name, pt, ct)
                try:
                    await _finalize(
                        conversation_id=conversation_id,
                        project_id=project_id,
                        user_id=user_id,
                        model_name=model_name,
                        resolved=resolved,
                        text=text,
                        pt=pt,
                        ct=ct,
                        raw_cost=raw_cost,
                    )
                except Exception:
                    logger.warning("중단 후 과금 실패 conv=%s", conversation_id, exc_info=True)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
