"""빌트인 AI 채팅 사용자 메모리 API — 장기 기억(프로젝트 무관, user_id 소유)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_token_info
from app.services.chat import memory_store as ms

router = APIRouter()

_MAX_CONTENT = 4000


class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=_MAX_CONTENT)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, max_length=_MAX_CONTENT)
    is_active: bool | None = None


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ms.MemoryNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ms.MemoryForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ms.MemoryValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


@router.post("/memories", status_code=201)
async def create_memory(payload: MemoryCreate, token_info: dict = Depends(get_token_info)):
    try:
        return await ms.create_memory(user_id=token_info["user_id"], content=payload.content)
    except (ms.MemoryValidationError, ms.ChatStorageUnavailable) as exc:
        raise _map_error(exc) from exc


@router.get("/memories")
async def list_memories(token_info: dict = Depends(get_token_info)):
    try:
        return await ms.list_memories(user_id=token_info["user_id"])
    except ms.ChatStorageUnavailable as exc:
        raise _map_error(exc) from exc


@router.patch("/memories/{memory_id}")
async def update_memory(memory_id: int, payload: MemoryUpdate, token_info: dict = Depends(get_token_info)):
    try:
        return await ms.update_memory(
            memory_id, user_id=token_info["user_id"], patch=payload.model_dump(exclude_unset=True)
        )
    except (ms.MemoryNotFound, ms.MemoryForbidden, ms.MemoryValidationError, ms.ChatStorageUnavailable) as exc:
        raise _map_error(exc) from exc


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: int, token_info: dict = Depends(get_token_info)):
    try:
        await ms.delete_memory(memory_id, user_id=token_info["user_id"])
    except (ms.MemoryNotFound, ms.MemoryForbidden, ms.ChatStorageUnavailable) as exc:
        raise _map_error(exc) from exc
