"""Union Mount 레이어 시스템 REST API 엔드포인트."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_os_conn, get_token_info
from app.database import get_session
from app.models.union import (
    AncestorChain,
    BuilderAccessInfo,
    BuilderAccessRequest,
    CreateLayerRequest,
    CreateTemplateRequest,
    LayerInfo,
    MountInfo,
    RecordMountRequest,
    SealLayerResponse,
    StorageStats,
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
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 목록 조회 (페이지네이션, 이름 필터 지원, 프로젝트 격리 적용)."""
    is_admin = token_info.get("is_system_admin", False)
    project_id = token_info.get("project_id") or None
    return await union_layers.list_layers(
        session,
        name=name,
        project_id=project_id,
        is_admin=is_admin,
        limit=limit,
        offset=offset,
    )


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
    project_id = token_info.get("project_id") or None
    try:
        return await union_layers.create_layer(session, req, created_by=created_by, project_id=project_id)
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


# ---------------------------------------------------------------------------
# 마운트 추적
# ---------------------------------------------------------------------------


@router.post("/mounts", response_model=MountInfo, status_code=201)
async def record_mount(
    req: RecordMountRequest,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """마운트 기록 추가. user_id는 토큰에서 자동 추출."""
    user_id = token_info.get("user_id") or token_info.get("username") or "unknown"
    try:
        return await union_layers.record_mount(session, user_id, req.vm_hostname, req.leaf_layer_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/mounts/{mount_id}/unmount", response_model=MountInfo)
async def record_unmount(
    mount_id: int,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """마운트 해제 기록. 본인 마운트만 해제 가능."""
    user_id = token_info.get("user_id") or token_info.get("username") or "unknown"
    try:
        return await union_layers.record_unmount(session, mount_id, user_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ---------------------------------------------------------------------------
# 스토리지 통계
# ---------------------------------------------------------------------------


@router.get("/stats/storage", response_model=StorageStats)
async def get_storage_stats(
    _token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 스토리지 사용량 통계 (전체, 봉인/미봉인, 크기, 파일 수)."""
    return await union_layers.get_storage_stats(session)


# ---------------------------------------------------------------------------
# Builder CephX 접근 관리 (관리자 전용)
# ---------------------------------------------------------------------------


@router.post("/builder/access", response_model=BuilderAccessInfo, status_code=201)
async def grant_builder_access(
    req: BuilderAccessRequest,
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """빌더 VM에 layer-store-rw CephX 접근 권한 부여 (관리자 전용)."""
    _require_admin(token_info)

    from app.config import get_settings
    from app.services import manila

    settings = get_settings()
    share_id = settings.union_layer_store_rw_share_id
    if not share_id:
        raise HTTPException(status_code=503, detail="union_layer_store_rw_share_id가 설정되지 않았습니다")

    try:
        rule = await __import__("asyncio").to_thread(
            manila.create_access_rule,
            conn,
            share_id,
            req.cephx_user,
            req.access_level,
            "cephx",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Manila access rule 생성 실패: {e}")

    return BuilderAccessInfo(
        access_id=rule["access_id"],
        cephx_user=req.cephx_user,
        access_level=req.access_level,
        share_id=share_id,
    )


@router.delete("/builder/access/{access_id}", status_code=204)
async def revoke_builder_access(
    access_id: str,
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """빌더 VM CephX 접근 권한 회수 (관리자 전용)."""
    _require_admin(token_info)

    from app.config import get_settings
    from app.services import manila

    settings = get_settings()
    share_id = settings.union_layer_store_rw_share_id
    if not share_id:
        raise HTTPException(status_code=503, detail="union_layer_store_rw_share_id가 설정되지 않았습니다")

    try:
        await __import__("asyncio").to_thread(manila.revoke_access_rule, conn, share_id, access_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Manila access rule 회수 실패: {e}")
