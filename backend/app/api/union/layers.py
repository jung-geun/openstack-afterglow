"""Union Mount 레이어 시스템 REST API 엔드포인트."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_token_info
from app.database import get_session
from app.models.union import (
    AncestorChain,
    CreateLayerRequest,
    CreateTemplateRequest,
    LayerInfo,
    SealLayerResponse,
    TemplateInfo,
)
from app.services import union_layers

router = APIRouter()
_logger = logging.getLogger(__name__)


def _require_admin(token_info: dict) -> None:
    """관리자 권한 확인. 아니면 403."""
    if not token_info.get("is_system_admin", False):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")


@router.get("/layers", response_model=list[LayerInfo])
async def list_layers(
    name: str | None = Query(default=None, description="이름 필터"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 목록 조회 (페이지네이션, 이름 필터 지원)."""
    return await union_layers.list_layers(session, name=name, limit=limit, offset=offset)


@router.post("/layers/{layer_id}/seal", response_model=SealLayerResponse)
async def seal_layer(
    layer_id: str,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 봉인 (관리자 전용). 봉인 후 수정 불가."""
    _require_admin(token_info)
    try:
        return await union_layers.seal_layer(session, layer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/layers/{layer_id}/dependents", response_model=list[LayerInfo])
async def get_dependents(
    layer_id: str,
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """직접 자식 레이어 목록 조회."""
    try:
        return await union_layers.get_dependents(session, layer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/layers/{layer_id}/ancestors", response_model=AncestorChain)
async def get_ancestors(
    layer_id: str,
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """조상 체인 조회 (base-first 순서). overlayfs lowerdir 조립에 사용."""
    try:
        return await union_layers.get_ancestors(session, layer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/layers/{layer_id}", response_model=LayerInfo)
async def get_layer(
    layer_id: str,
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 상세 조회."""
    layer = await union_layers.get_layer(session, layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail=f"레이어 {layer_id}를 찾을 수 없습니다")
    return layer


@router.delete("/layers/{layer_id}", status_code=204)
async def delete_layer(
    layer_id: str,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 삭제 (관리자 전용). 자식/템플릿 참조/활성 마운트가 있으면 409."""
    _require_admin(token_info)
    try:
        await union_layers.delete_layer(session, layer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/layers", response_model=LayerInfo, status_code=201)
async def create_layer(
    req: CreateLayerRequest,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """새 레이어 등록 (관리자 전용)."""
    _require_admin(token_info)
    created_by = token_info.get("username") or token_info.get("user_id") or "unknown"
    try:
        return await union_layers.create_layer(session, req, created_by=created_by)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/templates", response_model=list[TemplateInfo])
async def list_templates(
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """템플릿 목록 조회."""
    return await union_layers.list_templates(session)


@router.get("/templates/{name}/{version}", response_model=TemplateInfo)
async def get_template_detail(
    name: str,
    version: int,
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """템플릿 상세 조회 (resolved_stack 포함)."""
    result = await union_layers.get_template(session, name, version)
    if result is None:
        raise HTTPException(status_code=404, detail=f"템플릿 {name}@{version}을 찾을 수 없습니다")
    return result


@router.post("/templates", response_model=TemplateInfo, status_code=201)
async def create_template(
    req: CreateTemplateRequest,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """새 템플릿 생성 (관리자 전용)."""
    _require_admin(token_info)
    created_by = token_info.get("username") or token_info.get("user_id") or "unknown"
    try:
        return await union_layers.create_template(session, req, created_by=created_by)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
