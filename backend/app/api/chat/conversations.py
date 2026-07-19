"""빌트인 AI 채팅 대화/메시지 API (사용자 소유 리소스).

전 엔드포인트 get_token_info 인증 + user_id 소유권 검증(IDOR 방어, 프로젝트 무관).
서비스(conversation_store)가 소유권을 강제하고, 예외를 HTTP 상태로 매핑한다.
project_id 는 생성 시점 메타로만 저장되고 소유권 판정에는 쓰지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_token_info
from app.services.chat import conversation_store as cs
from app.services.chat import provider_store

router = APIRouter()


class AvailableModel(BaseModel):
    model_name: str
    display_name: str

    model_config = {"protected_namespaces": ()}


@router.get("/models", response_model=list[AvailableModel])
async def list_available_models(token_info: dict = Depends(get_token_info)):
    """사용자용 활성 모델 카탈로그(키·가격 미포함). 저장소 장애 시 빈 목록(graceful)."""
    try:
        models = await provider_store.list_models(active_only=True)
    except provider_store.ChatStorageUnavailable:
        return []
    return [{"model_name": m["model_name"], "display_name": m.get("display_name") or m["model_name"]} for m in models]


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    model_name: str | None = Field(default=None, max_length=190)

    model_config = {"protected_namespaces": ()}


class ConversationResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    title: str | None
    model_name: str | None
    created_at: str | None
    updated_at: str | None

    model_config = {"protected_namespaces": ()}


class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str | None
    tool_calls: list | None
    token_prompt: int
    token_completion: int
    created_at: str | None


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, cs.ConversationNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, cs.ConversationForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(payload: ConversationCreateRequest, token_info: dict = Depends(get_token_info)):
    try:
        return await cs.create_conversation(
            project_id=token_info["project_id"],
            user_id=token_info["user_id"],
            title=payload.title,
            model_name=payload.model_name,
        )
    except cs.ChatStorageUnavailable as exc:
        raise _map_error(exc) from exc


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(limit: int = 50, offset: int = 0, token_info: dict = Depends(get_token_info)):
    try:
        return await cs.list_conversations(user_id=token_info["user_id"], limit=limit, offset=offset)
    except cs.ChatStorageUnavailable as exc:
        raise _map_error(exc) from exc


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, token_info: dict = Depends(get_token_info)):
    try:
        return await cs.get_conversation(conversation_id, user_id=token_info["user_id"])
    except (cs.ConversationNotFound, cs.ConversationForbidden, cs.ChatStorageUnavailable) as exc:
        raise _map_error(exc) from exc


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, token_info: dict = Depends(get_token_info)):
    try:
        await cs.delete_conversation(conversation_id, user_id=token_info["user_id"])
    except (cs.ConversationNotFound, cs.ConversationForbidden, cs.ChatStorageUnavailable) as exc:
        raise _map_error(exc) from exc


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: str, limit: int = 200, offset: int = 0, token_info: dict = Depends(get_token_info)
):
    try:
        return await cs.list_messages(conversation_id, user_id=token_info["user_id"], limit=limit, offset=offset)
    except (cs.ConversationNotFound, cs.ConversationForbidden, cs.ChatStorageUnavailable) as exc:
        raise _map_error(exc) from exc
