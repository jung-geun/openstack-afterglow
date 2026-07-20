"""빌트인 AI 채팅 스트리밍 completions (SSE) — 메시지 버전 트리.

흐름: precheck(fail-closed) → 대화 소유권(user_id) → resolve_model 화이트리스트 → 활성 경로 로드 →
user 메시지 저장(parent=active_leaf) → engine.stream → parent 체인으로 메시지 저장 + active_leaf 갱신 + 과금.
재생성은 대상 답변의 턴-시작 user 아래에 새 assistant 형제를 만든다(다른 모델 가능, active_leaf 이동).

⚠️ 과금은 정상 완료·중단 무관하게 정확히 1회. 모델 replay 에서 role=tool 은 제외(orphaned tool 400 방지).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTasks

from app.api.deps import get_token_info
from app.config import get_settings
from app.services.chat import agent_store as ags
from app.services.chat import attachments as att
from app.services.chat import conversation_store as cs
from app.services.chat import credit, engine, litellm_client, memory_extract, title_summary
from app.services.chat import memory_store as ms
from app.services.chat import provider_store as ps
from app.services.chat import workspace_store as ws

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_TOKENS_CAP = 4096
_MAX_MESSAGE_CHARS = 32000


class AttachmentRef(BaseModel):
    """채팅 첨부 참조(POST /chat/attachments 반환값). 현재는 이미지 전용."""

    key: str = Field(..., max_length=300)
    mime: str = Field(..., max_length=100)
    name: str = Field(default="", max_length=256)


_MAX_ATTACHMENTS = 8


class CompletionRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_CHARS)
    attachments: list[AttachmentRef] = Field(default_factory=list, max_length=_MAX_ATTACHMENTS)
    model: str | None = Field(default=None, max_length=190)
    agent_id: int | None = Field(default=None)  # 에이전트 바인딩(instructions·모델·파라미터)
    max_tokens: int | None = Field(default=None, ge=1, le=_MAX_TOKENS_CAP)
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: str | None = Field(default=None, max_length=20)  # 요청별 추론 강도(없으면 전역 기본)
    # 대화별 tool/MCP 선택(None=활성 전체, []=없음, [id...]=해당 항목만). 에이전트 바인딩 시 에이전트 우선.
    tool_ids: list[int] | None = Field(default=None)
    mcp_ids: list[int] | None = Field(default=None)

    model_config = {"protected_namespaces": ()}


class RegenerateRequest(BaseModel):
    model: str | None = Field(default=None, max_length=190)
    agent_id: int | None = Field(default=None)
    max_tokens: int | None = Field(default=None, ge=1, le=_MAX_TOKENS_CAP)
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: str | None = Field(default=None, max_length=20)  # 요청별 추론 강도(없으면 전역 기본)
    # 대화별 tool/MCP 선택(None=활성 전체, []=없음, [id...]=해당 항목만). 에이전트 바인딩 시 에이전트 우선.
    tool_ids: list[int] | None = Field(default=None)
    mcp_ids: list[int] | None = Field(default=None)

    model_config = {"protected_namespaces": ()}


_MAX_TEMP_MESSAGES = 40


class TempMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_CHARS)


class TempCompletionRequest(BaseModel):
    """임시 채팅 — conversation 없이 메시지 배열로 stateless 스트리밍(미저장)."""

    messages: list[TempMessage] = Field(..., min_length=1, max_length=_MAX_TEMP_MESSAGES)
    attachments: list[AttachmentRef] = Field(default_factory=list, max_length=_MAX_ATTACHMENTS)
    model: str | None = Field(default=None, max_length=190)
    max_tokens: int | None = Field(default=None, ge=1, le=_MAX_TOKENS_CAP)
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: str | None = Field(default=None, max_length=20)  # 요청별 추론 강도(없으면 전역 기본)
    # 대화별 tool/MCP 선택(None=활성 전체, []=없음, [id...]=해당 항목만). 에이전트 바인딩 시 에이전트 우선.
    tool_ids: list[int] | None = Field(default=None)
    mcp_ids: list[int] | None = Field(default=None)

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


def _tool_selection(agent: dict | None, payload_tool_ids, payload_mcp_ids):
    """대화별 tool/MCP 선택 계산 — 에이전트 바인딩 시 에이전트가 tool set 소유(빈=제한 없음).

    반환: (selected_tool_ids, selected_mcp_ids) 각각 tuple 또는 None(=활성 전체).
    """
    if agent:
        at = agent.get("tool_ids") or None
        am = agent.get("mcp_ids") or None
        return (tuple(at) if at else None, tuple(am) if am else None)
    return (
        tuple(payload_tool_ids) if payload_tool_ids is not None else None,
        tuple(payload_mcp_ids) if payload_mcp_ids is not None else None,
    )


async def _apply_attachments(
    input_messages: list[dict], attachments: list, resolved: dict, token_info: dict
) -> list[dict]:
    """마지막 user 턴을 멀티모달 content 로 교체(vision 모델 + 이미지 첨부 시). 현재 턴만(과거는 텍스트).

    각 첨부는 presigned URL(실패 시 base64) 로 해석. boto3 동기 I/O 라 to_thread.
    """
    if not attachments or not input_messages:
        return input_messages
    caps = resolved.get("capabilities") or {}
    if not caps.get("vision"):
        return input_messages
    parts: list[dict] = [{"type": "text", "text": input_messages[-1].get("content") or ""}]
    for a in attachments:
        if not att.is_image(a.mime):
            continue
        url = await asyncio.to_thread(
            att.resolve_image_url,
            token_info["token"],
            token_info["user_id"],
            token_info["project_id"],
            a.key,
            a.mime,
        )
        if url:
            parts.append({"type": "image_url", "image_url": {"url": url}})
    if len(parts) > 1:
        input_messages[-1]["content"] = parts
    return input_messages


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


async def _resolve_agent(agent_id: int | None, user_id: str) -> dict | None:
    """agent_id 가 주어지면 실행 설정(instructions·model·params) 로드. 접근 불가/미존재 시 404."""
    if agent_id is None:
        return None
    try:
        agent = await ags.get_agent_for_run(agent_id, user_id=user_id)
    except ags.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if agent is None:
        raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없거나 접근 권한이 없습니다")
    return agent


async def _load_context(conv: dict, user_id: str) -> tuple[str | None, list[str]]:
    """대화 소속 프로젝트(workspace) 지침 + 사용자 활성 메모리 로드. 부가 기능이라 실패는 무시."""
    workspace_instr = None
    try:
        workspace_instr = await ws.get_instructions_for_run(conv.get("workspace_id"), user_id=user_id)
    except Exception:
        logger.warning("워크스페이스 지침 로드 실패", exc_info=True)
    memories = await ms.active_contents_for_run(user_id=user_id)  # 자체 예외 흡수(빈 목록)
    return workspace_instr, memories


def _apply_context(
    agent: dict | None,
    workspace_instr: str | None,
    memories: list[str],
    input_messages: list[dict],
    temperature,
    max_tokens_req,
):
    """system 선주입 컨텍스트 구성 — 메모리 → 프로젝트 지침 → 에이전트 지침(구체적일수록 뒤).

    런타임 주입일 뿐 chat_messages 에는 저장하지 않는다(활성 경로 불변). params 는 에이전트에서만.
    반환: (messages, temperature, max_tokens_req)
    """
    preamble: list[dict] = []
    if memories:
        joined = "\n".join(f"- {m}" for m in memories)
        preamble.append({"role": "system", "content": f"사용자에 대해 기억할 사실:\n{joined}"})
    if workspace_instr:
        preamble.append({"role": "system", "content": workspace_instr})
    if agent and agent.get("instructions"):
        preamble.append({"role": "system", "content": agent["instructions"]})
    if preamble:
        input_messages = [*preamble, *input_messages]
    params = (agent or {}).get("params") or {}
    if temperature is None:
        temperature = params.get("temperature")
    if max_tokens_req is None:
        max_tokens_req = params.get("max_tokens")
    return input_messages, temperature, max_tokens_req


async def _stream_and_persist(
    *,
    conversation_id: str | None,
    project_id: str,
    user_id: str,
    model_name: str,
    resolved: dict,
    input_messages: list[dict],
    start_parent_id: int | None,
    max_tokens: int | None,
    temperature: float | None,
    persist: bool = True,
    reasoning_effort: str | None = None,
    selected_tool_ids: tuple[int, ...] | None = None,
    selected_mcp_ids: tuple[int, ...] | None = None,
):
    """engine.stream 을 소비해 SSE 를 yield 하고, parent 체인으로 메시지 저장 + active_leaf + 과금.

    start_parent_id 는 이 응답 턴의 부모(신규: 방금 저장한 user 메시지 / 재생성: 턴-시작 user).
    persist=False(임시 채팅)면 메시지를 저장하지 않고 과금(usage_logs)만 한다(conversation_id=None).
    """
    parts: list[str] = []
    reasoning_parts: list[str] = []
    final_usage = None
    final_citations: list | None = None
    charged = False
    errored = False
    state = {"last_parent": start_parent_id}
    _do_persist = persist and conversation_id is not None
    event_id = str(uuid.uuid4())
    input_price_per_token = resolved.get("input_price_per_token")
    output_price_per_token = resolved.get("output_price_per_token")
    price_source = resolved.get("price_source")

    async def _save(role: str, content, tool_calls=None, citations=None, reasoning=None, is_leaf: bool = False):
        if not _do_persist:
            return {"id": None}
        msg = await cs.add_message(
            conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            citations=citations,
            reasoning=reasoning,
            parent_id=state["last_parent"],
            model_name=(model_name if role == "assistant" else None),
            set_leaf=is_leaf,
        )
        state["last_parent"] = msg["id"]
        return msg

    async def _finalize(text: str, pt: int, ct: int, usage_cost: litellm_client.UsageCost):
        if text and _do_persist:
            try:
                await _save(
                    "assistant",
                    text,
                    citations=final_citations,
                    reasoning=("".join(reasoning_parts) or None),
                    is_leaf=True,
                )
            except Exception:
                logger.warning("assistant 메시지 저장 실패 conv=%s", conversation_id, exc_info=True)
        return await credit.apply_usage(
            event_id=event_id,
            user_id=user_id,
            project_id=project_id,
            model_name=model_name,
            provider=resolved.get("provider_name"),
            prompt_tokens=pt,
            completion_tokens=ct,
            usage_cost=usage_cost,
            margin_multiplier=resolved["margin_multiplier"],
            conversation_id=conversation_id,
            source="web",
        )

    # 요청별 effort 우선, 없으면 전역 기본. (litellm_client 가 지원 모델에만 적용)
    reasoning_effort = reasoning_effort or get_settings().chat_reasoning_effort
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
            reasoning_effort=reasoning_effort,
            selected_tool_ids=selected_tool_ids,
            selected_mcp_ids=selected_mcp_ids,
        ):
            etype = ev.get("type")
            if etype == "token":
                parts.append(ev["text"])
                yield _sse({"type": "token", "text": ev["text"]})
            elif etype == "reasoning":
                # 추론(thinking) 델타 — 라이브 중계 + 누적(최종 답변에 저장해 재로딩 시 유지).
                rtext = ev.get("text", "")
                reasoning_parts.append(rtext)
                yield _sse({"type": "reasoning", "text": rtext})
            elif etype == "tool_call":
                yield _sse({"type": "tool_call", "name": ev.get("name")})
            elif etype == "assistant_tool_calls":
                # 이 스텝 텍스트는 이 메시지로 저장 — 최종 답변 parts 에서 제외(중복 방지).
                parts.clear()
                # 시각화용 SSE 중계 — 툴 호출(이름·인자)을 프론트가 카드로 표시. content 는 선행 사유.
                yield _sse(
                    {
                        "type": "tool_calls",
                        "content": ev.get("content"),
                        "calls": [
                            {"id": tc.get("id"), "name": tc.get("name"), "args": tc.get("args")}
                            for tc in (ev.get("tool_calls") or [])
                        ],
                    }
                )
                try:
                    await _save("assistant", ev.get("content"), tool_calls=ev.get("tool_calls"))
                except Exception:
                    logger.warning("assistant tool_calls 저장 실패 conv=%s", conversation_id, exc_info=True)
            elif etype == "tool_result":
                # 시각화용 SSE 중계 — 툴 실행 결과를 프론트가 카드에 채운다.
                yield _sse(
                    {
                        "type": "tool_result",
                        "tool_call_id": ev.get("tool_call_id"),
                        "name": ev.get("name"),
                        "content": ev.get("content"),
                    }
                )
                try:
                    await _save(
                        "tool",
                        ev.get("content"),
                        tool_calls=[{"tool_call_id": ev.get("tool_call_id"), "name": ev.get("name")}],
                    )
                except Exception:
                    logger.warning("tool_result 저장 실패 conv=%s", conversation_id, exc_info=True)
            elif etype == "citations":
                # 출처 — 최종 답변에 저장(_finalize) + 라이브 SSE 중계.
                final_citations = ev.get("items")
                yield _sse({"type": "citations", "items": final_citations})
            elif etype == "usage":
                final_usage = ev.get("usage")
            elif etype == "error":
                errored = True
                yield _sse({"type": "error", "message": ev.get("message", "오류")})

        if not errored:
            text = "".join(parts)
            pt, ct = litellm_client.extract_usage(model_name, input_messages, text, final_usage)
            usage_cost = litellm_client.cost_from_usage(
                model_name,
                pt,
                ct,
                input_price_per_token=input_price_per_token,
                output_price_per_token=output_price_per_token,
                price_source=price_source,
                provider_type=resolved.get("provider_type"),
            )
            credited = await _finalize(text, pt, ct, usage_cost)
            charged = True
            yield _sse({"type": "done", "prompt_tokens": pt, "completion_tokens": ct, "credited_cost": float(credited)})
    finally:
        # 중단(disconnect) 등 비정상 종료 시에도 부분 사용량을 과금(정확히 1회). 모델 하드 실패는 제외.
        if not charged and not errored and parts:
            text = "".join(parts)
            pt, ct = litellm_client.extract_usage(model_name, input_messages, text, final_usage)
            usage_cost = litellm_client.cost_from_usage(
                model_name,
                pt,
                ct,
                input_price_per_token=input_price_per_token,
                output_price_per_token=output_price_per_token,
                price_source=price_source,
                provider_type=resolved.get("provider_type"),
            )
            try:
                await _finalize(text, pt, ct, usage_cost)
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
    agent = await _resolve_agent(payload.agent_id, user_id)
    model_name = (
        payload.model or (agent or {}).get("model_name") or conv.get("model_name") or settings.chat_default_model
    )
    resolved = await _resolve_model(model_name)

    # 활성 경로 로드 + user 메시지 저장(parent=active_leaf, 새 리프)
    try:
        path = await cs.get_active_path(conversation_id, user_id=user_id)
        user_msg = await cs.add_message(
            conversation_id,
            role="user",
            content=payload.message,
            attachments=([a.model_dump() for a in payload.attachments] or None),
            parent_id=path["active_leaf_id"],
            set_leaf=True,
        )
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    input_messages = _model_input(path["messages"], extra_user=payload.message)
    workspace_instr, memories = await _load_context(conv, user_id)
    input_messages, temperature, max_tokens_req = _apply_context(
        agent, workspace_instr, memories, input_messages, payload.temperature, payload.max_tokens
    )
    # 현재 user 턴에 이미지 첨부를 멀티모달 content 로 주입(vision 모델만).
    input_messages = await _apply_attachments(input_messages, payload.attachments, resolved, token_info)
    max_tokens = min(max_tokens_req or _MAX_TOKENS_CAP, _MAX_TOKENS_CAP)
    _sel_tools, _sel_mcps = _tool_selection(agent, payload.tool_ids, payload.mcp_ids)

    gen = _stream_and_persist(
        conversation_id=conversation_id,
        project_id=project_id,
        user_id=user_id,
        model_name=model_name,
        resolved=resolved,
        input_messages=input_messages,
        start_parent_id=user_msg["id"],
        max_tokens=max_tokens,
        temperature=temperature,
        reasoning_effort=payload.reasoning_effort,
        selected_tool_ids=_sel_tools,
        selected_mcp_ids=_sel_mcps,
    )
    # SSE 종료 후 백그라운드: 제목 요약 + 사용자 메모리 자동 추출(둘 다 시스템 부담, 실패 무시).
    # temp/regenerate 에는 붙이지 않는다(temp=휘발성, regenerate=중복 추출 방지).
    tasks = BackgroundTasks()
    tasks.add_task(
        title_summary.generate_title_if_absent,
        conversation_id=conversation_id,
        project_id=project_id,
        user_id=user_id,
    )
    tasks.add_task(
        memory_extract.generate_memory_if_applicable,
        conversation_id=conversation_id,
        project_id=project_id,
        user_id=user_id,
    )
    return StreamingResponse(gen, media_type="text/event-stream", background=tasks)


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

    agent = await _resolve_agent(payload.agent_id, user_id)
    model_name = (
        payload.model or (agent or {}).get("model_name") or conv.get("model_name") or settings.chat_default_model
    )
    resolved = await _resolve_model(model_name)

    try:
        path_msgs = await cs.path_ending_at(conversation_id, user_id=user_id, message_id=turn_user["id"])
    except cs.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    input_messages = _model_input(path_msgs)  # 경로 마지막이 turn_user(role=user)
    workspace_instr, memories = await _load_context(conv, user_id)
    input_messages, temperature, max_tokens_req = _apply_context(
        agent, workspace_instr, memories, input_messages, payload.temperature, payload.max_tokens
    )
    max_tokens = min(max_tokens_req or _MAX_TOKENS_CAP, _MAX_TOKENS_CAP)
    _sel_tools, _sel_mcps = _tool_selection(agent, payload.tool_ids, payload.mcp_ids)

    gen = _stream_and_persist(
        conversation_id=conversation_id,
        project_id=project_id,
        user_id=user_id,
        model_name=model_name,
        resolved=resolved,
        input_messages=input_messages,
        start_parent_id=turn_user["id"],
        max_tokens=max_tokens,
        temperature=temperature,
        reasoning_effort=payload.reasoning_effort,
        selected_tool_ids=_sel_tools,
        selected_mcp_ids=_sel_mcps,
    )
    return StreamingResponse(gen, media_type="text/event-stream")


@router.post("/temp-completions")
async def temp_completion(payload: TempCompletionRequest, token_info: dict = Depends(get_token_info)):
    """임시 채팅 — conversation 없이 메시지 배열로 스트리밍. 미저장, 과금은 유지(source=web)."""
    settings = get_settings()
    project_id = token_info["project_id"]
    user_id = token_info["user_id"]

    try:
        await credit.precheck(user_id, project_id)
    except credit.QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except credit.ChatStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    model_name = payload.model or settings.chat_default_model
    resolved = await _resolve_model(model_name)

    input_messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    input_messages = await _apply_attachments(input_messages, payload.attachments, resolved, token_info)
    max_tokens = min(payload.max_tokens or _MAX_TOKENS_CAP, _MAX_TOKENS_CAP)
    _sel_tools, _sel_mcps = _tool_selection(None, payload.tool_ids, payload.mcp_ids)

    gen = _stream_and_persist(
        conversation_id=None,
        project_id=project_id,
        user_id=user_id,
        model_name=model_name,
        resolved=resolved,
        input_messages=input_messages,
        start_parent_id=None,
        max_tokens=max_tokens,
        temperature=payload.temperature,
        persist=False,
        reasoning_effort=payload.reasoning_effort,
        selected_tool_ids=_sel_tools,
        selected_mcp_ids=_sel_mcps,
    )
    return StreamingResponse(gen, media_type="text/event-stream")
