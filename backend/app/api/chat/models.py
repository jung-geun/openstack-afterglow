"""빌트인 AI 채팅 관리자 — LLM 프로바이더/모델 CRUD. 전 엔드포인트 require_admin.

프로바이더 api_key 는 요청으로만 받고 응답에는 절대 반환하지 않는다(has_api_key 불리언만).
서비스 계층(provider_store)이 AES-256-GCM 으로 암호화 저장한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.services.chat import model_discovery
from app.services.chat import provider_store as ps

router = APIRouter(dependencies=[Depends(require_admin)])


# --- 프로바이더 ---
class ProviderCreateRequest(BaseModel):
    name: str = Field(..., max_length=100)
    provider_type: str = Field(default="openai", max_length=40)  # litellm custom_llm_provider
    api_base: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=500)
    margin_multiplier: float = Field(default=1.0, ge=0)
    is_active: bool = True


class ProviderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    provider_type: str | None = Field(default=None, max_length=40)
    api_base: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=500)
    margin_multiplier: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    api_base: str | None
    has_api_key: bool
    is_active: bool
    margin_multiplier: float
    created_at: str | None
    updated_at: str | None


# --- 모델 ---
class ModelCreateRequest(BaseModel):
    provider_id: int
    model_name: str = Field(..., max_length=190)
    display_name: str | None = Field(default=None, max_length=150)
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)
    is_active: bool = True

    model_config = {"protected_namespaces": ()}


class ModelUpdateRequest(BaseModel):
    model_name: str | None = Field(default=None, max_length=190)
    display_name: str | None = Field(default=None, max_length=150)
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None

    model_config = {"protected_namespaces": ()}  # model_name 필드 경고 억제


class ModelResponse(BaseModel):
    id: int
    provider_id: int
    model_name: str
    display_name: str | None
    is_active: bool
    input_price: float | None
    output_price: float | None
    created_at: str | None
    updated_at: str | None

    model_config = {"protected_namespaces": ()}


def _map_storage(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# 프로바이더 엔드포인트
# ---------------------------------------------------------------------------
@router.get("/admin/providers", response_model=list[ProviderResponse])
async def list_providers():
    try:
        return await ps.list_providers()
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.post("/admin/providers", response_model=ProviderResponse, status_code=201)
async def create_provider(payload: ProviderCreateRequest):
    try:
        return await ps.create_provider(**payload.model_dump())
    except ps.ProviderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.patch("/admin/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(provider_id: int, payload: ProviderUpdateRequest):
    try:
        return await ps.update_provider(provider_id, payload.model_dump(exclude_unset=True))
    except ps.ProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ps.ProviderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.delete("/admin/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: int):
    try:
        await ps.delete_provider(provider_id)
    except ps.ProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.get("/admin/providers/{provider_id}/available-models")
async def available_models(provider_id: int):
    """프로바이더 API(또는 litellm 정적 목록)에서 사용 가능한 모델 id 목록을 조회. 등록 전 선택/필터용."""
    try:
        return await model_discovery.discover_models(provider_id)
    except ps.ProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


# ---------------------------------------------------------------------------
# 모델 엔드포인트
# ---------------------------------------------------------------------------
@router.get("/admin/models", response_model=list[ModelResponse])
async def list_models(active_only: bool = False):
    try:
        return await ps.list_models(active_only=active_only)
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.post("/admin/models", response_model=ModelResponse, status_code=201)
async def create_model(payload: ModelCreateRequest):
    try:
        return await ps.create_model(**payload.model_dump())
    except ps.ProviderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.patch("/admin/models/{model_id}", response_model=ModelResponse)
async def update_model(model_id: int, payload: ModelUpdateRequest):
    try:
        return await ps.update_model(model_id, payload.model_dump(exclude_unset=True))
    except ps.ProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ps.ProviderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc


@router.delete("/admin/models/{model_id}", status_code=204)
async def delete_model(model_id: int):
    try:
        await ps.delete_model(model_id)
    except ps.ProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ps.ChatStorageUnavailable as exc:
        raise _map_storage(exc) from exc
