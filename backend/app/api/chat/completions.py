"""빌트인 AI 채팅 스트리밍 completions (SSE) — 메시지 버전 트리.

흐름: precheck(fail-closed) → 대화 소유권(user_id) → resolve_model 화이트리스트 → 활성 경로 로드 →
user 메시지 저장(parent=active_leaf) → engine.stream → parent 체인으로 메시지 저장 + active_leaf 갱신 + 과금.
재생성은 대상 답변의 턴-시작 user 아래에 새 assistant 형제를 만든다(다른 모델 가능, active_leaf 이동).

⚠️ 과금은 정상 완료·중단 무관하게 정확히 1회. 모델 replay 에서 role=tool 은 제외(orphaned tool 400 방지).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.api.deps import get_token_info
from app.config import get_settings
from app.services.chat import conversation_store as cs
from app.services.chat import credit, engine, litellm_client, title_summary
from app.services.chat import provider_store as ps

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_TOKENS_CAP = 4096
_MAX_MESSAGE_CHARS = 32000


class CompletionRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_CHARS)
    model: str | None = Field(default=None, max_length=190)
    max_tokens: int | None = Field(default=None, ge=1, le=_MAX_TOKENS_CAP)
    temperature: float | None = Field(default=None, ge=0, le=2)

    model_config = {"protected_namespaces": ()}


class RegenerateRequest(BaseModel):
    model: str | None = Field(default=None, max_length=190)
    max_tokens: int | None = Field(default=None, ge=1, le=_MAX_TOKENS_CAP)
    temperature: float | None = Field(default=None, ge=0, le=2)

    model_config = {"protected_namespaces": ()}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _model_input(path_messages: list[dict], extra_user: str | None = None) -> list[dict]:
    """활성 경로 메시지 → 모델 입력. role=tool 은 제외(orphaned tool 400 방지)."""
    msgs = [
        {"role": m["role"], "content": m["content"]} for m in path_messages if m.get("content") and m["role"] != "tool"
    ]
    if extra_user is not None:
        msgs.append({"role": "user", "content": extra_user})
    return msgs


async def _load_owned_conv(conversation_id: str, user_id: str) -> dict:
    try:
        return await cs.get_conversation(conversation_id, user_id=user_id)
    except cs.ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except cs.ConversationForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _resolve_model(model_name: str) -> dict:
    if not model_name:
        raise HTTPException(status_code=400, detail="모델이 지정되지 않았습니다")
    try:
        resolved = await ps.resolve_model(model_name)
    except ps.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if resolved is None:
        raise HTTPException(status_code=400, detail=f"허용되지 않은 모델입니다: {model_name}")
    return resolved


async def _stream_and_persist(
    *,
    conversation_id: str,
    project_id: str,
    user_id: str,
    model_name: str,
    resolved: dict,
    input_messages: list[dict],
    start_parent_id: int | None,
    max_tokens: int | None,
    temperature: float | None,
):
    """engine.stream 을 소비해 SSE 를 yield 하고, parent 체인으로 메시지 저장 + active_leaf + 과금.

    start_parent_id 는 이 응답 턴의 부모(신규: 방금 저장한 user 메시지 / 재생성: 턴-시작 user).
    """
    parts: list[str] = []
    final_usage = None
    charged = False
    errored = False
    state = {"last_parent": start_parent_id}

    async def _save(role: str, content, tool_calls=None, is_leaf: bool = False):
        msg = await cs.add_message(
            conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            parent_id=state["last_parent"],
            model_name=(model_name if role == "assistant" else None),
            set_leaf=is_leaf,
        )
        state["last_parent"] = msg["id"]
        return msg

    async def _finalize(text: str, pt: int, ct: int, raw_cost: float):
        if text:
            try:
                await _save("assistant", text, is_leaf=True)
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

    try:
        async for ev in engine.stream(
            model=model_name,
            messages=input_messages,
            project_id=project_id,
            user_id=user_id,
            custom_llm_provider=resolved.get("provider_type"),
            api_base=resolved.get("api_base"),
            api_key=resolved.get("api_key"),
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            etype = ev.get("type")
            if etype == "token":
                parts.append(ev["text"])
                yield _sse({"type": "token", "text": ev["text"]})
            elif etype == "tool_call":
                yield _sse({"type": "tool_call", "name": ev.get("name")})
            elif etype == "assistant_tool_calls":
                # 이 스텝 텍스트는 이 메시지로 저장 — 최종 답변 parts 에서 제외(중복 방지).
                parts.clear()
                try:
                    await _save("assistant", ev.get("content"), tool_calls=ev.get("tool_calls"))
                except Exception:
                    logger.warning("assistant tool_calls 저장 실패 conv=%s", conversation_id, exc_info=True)
            elif etype == "tool_result":
                try:
                    await _save(
                        "tool",
                        ev.get("content"),
                        tool_calls=[{"tool_call_id": ev.get("tool_call_id"), "name": ev.get("name")}],
                    )
                except Exception:
                    logger.warning("tool_result 저장 실패 conv=%s", conversation_id, exc_info=True)
            elif etype == "usage":
                final_usage = ev.get("usage")
            elif etype == "error":
                errored = True
                yield _sse({"type": "error", "message": ev.get("message", "오류")})

        if not errored:
            text = "".join(parts)
            pt, ct = litellm_client.extract_usage(model_name, input_messages, text, final_usage)
            raw_cost = litellm_client.cost_from_usage(model_name, pt, ct)
            credited = await _finalize(text, pt, ct, raw_cost)
            charged = True
            yield _sse({"type": "done", "prompt_tokens": pt, "completion_tokens": ct, "credited_cost": float(credited)})
    finally:
        # 중단(disconnect) 등 비정상 종료 시에도 부분 사용량을 과금(정확히 1회). 모델 하드 실패는 제외.
        if not charged and not errored and parts:
            text = "".join(parts)
            pt, ct = litellm_client.extract_usage(model_name, input_messages, text, final_usage)
            raw_cost = litellm_client.cost_from_usage(model_name, pt, ct)
            try:
                await _finalize(text, pt, ct, raw_cost)
            except Exception:
                logger.warning("중단 후 과금 실패 conv=%s", conversation_id, exc_info=True)


@router.post("/conversations/{conversation_id}/completions")
async def create_completion(
    conversation_id: str, payload: CompletionRequest, token_info: dict = Depends(get_token_info)
):
    settings = get_settings()
    project_id = token_info["project_id"]
    user_id = token_info["user_id"]

    try:
        await credit.precheck(user_id, project_id)
    except credit.QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except credit.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    conv = await _load_owned_conv(conversation_id, user_id)
    model_name = payload.model or conv.get("model_name") or settings.chat_default_model
    resolved = await _resolve_model(model_name)

    # 활성 경로 로드 + user 메시지 저장(parent=active_leaf, 새 리프)
    try:
        path = await cs.get_active_path(conversation_id, user_id=user_id)
        user_msg = await cs.add_message(
            conversation_id, role="user", content=payload.message, parent_id=path["active_leaf_id"], set_leaf=True
        )
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    input_messages = _model_input(path["messages"], extra_user=payload.message)
    max_tokens = min(payload.max_tokens or _MAX_TOKENS_CAP, _MAX_TOKENS_CAP)

    gen = _stream_and_persist(
        conversation_id=conversation_id,
        project_id=project_id,
        user_id=user_id,
        model_name=model_name,
        resolved=resolved,
        input_messages=input_messages,
        start_parent_id=user_msg["id"],
        max_tokens=max_tokens,
        temperature=payload.temperature,
    )
    title_task = BackgroundTask(
        title_summary.generate_title_if_absent, conversation_id=conversation_id, project_id=project_id, user_id=user_id
    )
    return StreamingResponse(gen, media_type="text/event-stream", background=title_task)


@router.post("/conversations/{conversation_id}/messages/{message_id}/regenerate")
async def regenerate_message(
    conversation_id: str, message_id: int, payload: RegenerateRequest, token_info: dict = Depends(get_token_info)
):
    """대상 답변의 턴-시작 user 아래에 새 assistant 형제를 생성(다른 모델 가능). active_leaf 이동."""
    settings = get_settings()
    project_id = token_info["project_id"]
    user_id = token_info["user_id"]

    try:
        await credit.precheck(user_id, project_id)
    except credit.QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except credit.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    conv = await _load_owned_conv(conversation_id, user_id)

    # 대상 답변의 턴-시작 user(분기점) 탐색
    try:
        turn_user = await cs.find_turn_start_user(conversation_id, user_id=user_id, message_id=message_id)
    except cs.ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except cs.ConversationForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if turn_user is None:
        raise HTTPException(status_code=400, detail="재생성할 사용자 턴을 찾을 수 없습니다")

    model_name = payload.model or conv.get("model_name") or settings.chat_default_model
    resolved = await _resolve_model(model_name)

    try:
        path_msgs = await cs.path_ending_at(conversation_id, user_id=user_id, message_id=turn_user["id"])
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    input_messages = _model_input(path_msgs)  # 경로 마지막이 turn_user(role=user)
    max_tokens = min(payload.max_tokens or _MAX_TOKENS_CAP, _MAX_TOKENS_CAP)

    gen = _stream_and_persist(
        conversation_id=conversation_id,
        project_id=project_id,
        user_id=user_id,
        model_name=model_name,
        resolved=resolved,
        input_messages=input_messages,
        start_parent_id=turn_user["id"],
        max_tokens=max_tokens,
        temperature=payload.temperature,
    )
    return StreamingResponse(gen, media_type="text/event-stream")
