"""Union Mount 레이어 시스템 REST API 엔드포인트."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.common.activity_recorder import rec
from app.api.deps import get_os_conn, get_token_info
from app.database import get_session
from app.models.union import (
    AncestorChain,
    BuilderAccessInfo,
    BuilderAccessRequest,
    CreateLayerRequest,
    CreateTemplateRequest,
    ForkLayerRequest,
    LayerInfo,
    MountInfo,
    RecordMountRequest,
    RestoreLayerRequest,
    SealLayerResponse,
    SnapshotLayerRequest,
    StorageStats,
    TemplateInfo,
)
from app.services import union_layers

router = APIRouter()
_logger = logging.getLogger(__name__)


async def _resolve_mount_user_id(request: Request) -> str:
    """record_mount/unmount 전용: Bearer(VM health) 토큰만 허용."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer ") :]
        from app.services import instance_health as _health_svc

        token_data = await _health_svc.verify_report_token(token)
        if not token_data:
            raise HTTPException(status_code=401, detail="유효하지 않은 Bearer 토큰")
        return f"vm:{token_data.get('instance_id', 'unknown')}"
    raise HTTPException(status_code=401, detail="Authorization Bearer 토큰이 필요합니다")


def _require_admin(token_info: dict) -> None:
    """관리자 권한 확인. 아니면 403."""
    if not token_info.get("is_system_admin", False):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")


def _can_access_layer(layer: "LayerInfo", token_info: dict) -> bool:
    """레이어 접근 권한 확인.

    - 관리자: 모든 레이어 접근 가능
    - 공유 레이어(project_id=None): 누구나 접근 가능
    - 프로젝트 레이어: 동일 project_id 사용자만 접근 가능
    """
    if token_info.get("is_system_admin", False):
        return True
    if layer.project_id is None:
        return True
    return layer.project_id == token_info.get("project_id")


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
        result = await union_layers.seal_layer(session, layer_id)
        await rec(token_info, None, resource_type="union_layer", action="seal", resource_id=layer_id)
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/layers/{layer_id}/fork", response_model=LayerInfo, status_code=201)
async def fork_layer(
    layer_id: str,
    req: ForkLayerRequest,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """봉인된 레이어에서 새 RW 레이어를 파생(fork)한다. 관리자 전용."""
    _require_admin(token_info)
    created_by = token_info.get("username") or token_info.get("user_id") or "unknown"
    project_id = token_info.get("project_id") or None
    try:
        return await union_layers.fork_layer(session, layer_id, req, created_by=created_by, project_id=project_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/layers/{layer_id}/snapshot", status_code=201)
async def snapshot_layer(
    layer_id: str,
    req: SnapshotLayerRequest,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
    conn=Depends(get_os_conn),
):
    """레이어 Manila share 스냅샷 생성. 관리자 전용."""
    _require_admin(token_info)
    try:
        return await union_layers.snapshot_layer(session, layer_id, req, conn)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스냅샷 생성 실패: {e}")


@router.post("/layers/{layer_id}/restore", status_code=204)
async def restore_layer(
    layer_id: str,
    req: RestoreLayerRequest,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
    conn=Depends(get_os_conn),
):
    """레이어 Manila share를 스냅샷 시점으로 복원. 관리자 전용."""
    _require_admin(token_info)
    try:
        await union_layers.restore_layer(session, layer_id, req, conn)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"복원 실패: {e}")


@router.get("/layers/{layer_id}/dependents", response_model=list[LayerInfo])
async def get_dependents(
    layer_id: str,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """직접 자식 레이어 목록 조회."""
    # 부모 레이어 소유권을 먼저 검증 (get_ancestors/get_layer 와 동일 패턴, early return)
    parent = await union_layers.get_layer(session, layer_id)
    if parent is None or not _can_access_layer(parent, token_info):
        raise HTTPException(status_code=404, detail=f"레이어 {layer_id}를 찾을 수 없습니다")
    try:
        result = await union_layers.get_dependents(session, layer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    # 공유 부모(project_id=None)의 자식이 타 프로젝트 소유일 수 있으므로 접근 가능한 자식만 반환
    return [child for child in result if _can_access_layer(child, token_info)]


@router.get("/layers/{layer_id}/ancestors", response_model=AncestorChain)
async def get_ancestors(
    layer_id: str,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """조상 체인 조회 (base-first 순서). overlayfs lowerdir 조립에 사용."""
    # 요청 레이어 소유권 검증
    leaf = await union_layers.get_layer(session, layer_id)
    if leaf is None or not _can_access_layer(leaf, token_info):
        raise HTTPException(status_code=404, detail=f"레이어 {layer_id}를 찾을 수 없습니다")
    try:
        return await union_layers.get_ancestors(session, layer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/layers/{layer_id}", response_model=LayerInfo)
async def get_layer(
    layer_id: str,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """레이어 상세 조회."""
    layer = await union_layers.get_layer(session, layer_id)
    if layer is None or not _can_access_layer(layer, token_info):
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
        await rec(token_info, None, resource_type="union_layer", action="delete", resource_id=layer_id)
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
        result = await union_layers.create_layer(session, req, created_by=created_by, project_id=project_id)
        await rec(
            token_info,
            None,
            resource_type="union_layer",
            action="create",
            resource_id=result.id,
            resource_name=req.name,
        )
        return result
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


@router.delete("/templates/{name}/{version}", status_code=204)
async def delete_template(
    name: str,
    version: int,
    token_info: dict = Depends(get_token_info),
    session=Depends(get_session),
):
    """템플릿 삭제 (관리자 전용). 미존재 시 404."""
    _require_admin(token_info)
    deleted = await union_layers.delete_template(session, name, version)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"템플릿 {name}@{version}을 찾을 수 없습니다")
    await rec(
        token_info,
        None,
        resource_type="union_template",
        action="delete",
        resource_name=f"{name}@{version}",
    )


# ---------------------------------------------------------------------------
# 마운트 추적
# ---------------------------------------------------------------------------


@router.post("/mounts", response_model=MountInfo, status_code=201)
async def record_mount(
    request: Request,
    req: RecordMountRequest,
    session=Depends(get_session),
):
    """마운트 기록 추가. VM Bearer 토큰만 허용."""
    user_id = await _resolve_mount_user_id(request)
    try:
        return await union_layers.record_mount(session, user_id, req.vm_hostname, req.leaf_layer_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/mounts/{mount_id}/unmount", response_model=MountInfo)
async def record_unmount(
    request: Request,
    mount_id: int,
    session=Depends(get_session),
):
    """마운트 해제 기록. 본인 마운트만 해제 가능."""
    user_id = await _resolve_mount_user_id(request)
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
        _logger.warning("Manila access rule 생성 실패: %s", e)

        raise HTTPException(status_code=502, detail="Manila access rule 생성 실패")

    return BuilderAccessInfo(
        access_id=rule["access_id"],
        cephx_user=req.cephx_user,
        access_level=req.access_level,
        share_id=share_id,
    )


@router.post("/user/access", response_model=BuilderAccessInfo, status_code=201)
async def grant_user_access(
    req: BuilderAccessRequest,
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """User VM에 layer-store-ro CephX 접근 권한 부여 (관리자 전용).

    union_layer_store_ro_share_id 미설정 시 503 반환.
    """
    _require_admin(token_info)

    from app.config import get_settings
    from app.services import manila

    settings = get_settings()
    share_id = settings.union_layer_store_ro_share_id
    if not share_id:
        raise HTTPException(status_code=503, detail="union_layer_store_ro_share_id가 설정되지 않았습니다")

    try:
        rule = await __import__("asyncio").to_thread(
            manila.create_access_rule,
            conn,
            share_id,
            req.cephx_user,
            "ro",
            "cephx",
        )
    except Exception as e:
        _logger.warning("User Manila access rule 생성 실패: %s", e)

        raise HTTPException(status_code=502, detail="Manila access rule 생성 실패")

    return BuilderAccessInfo(
        access_id=rule["access_id"],
        cephx_user=req.cephx_user,
        access_level="ro",
        share_id=share_id,
    )


@router.delete("/user/access/{access_id}", status_code=204)
async def revoke_user_access(
    access_id: str,
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """User VM CephX 접근 권한 회수 (관리자 전용)."""
    _require_admin(token_info)

    from app.config import get_settings
    from app.services import manila

    settings = get_settings()
    share_id = settings.union_layer_store_ro_share_id
    if not share_id:
        raise HTTPException(status_code=503, detail="union_layer_store_ro_share_id가 설정되지 않았습니다")

    try:
        await __import__("asyncio").to_thread(manila.revoke_access_rule, conn, share_id, access_id)
    except Exception as e:
        _logger.warning("User Manila access rule 회수 실패: %s", e)

        raise HTTPException(status_code=502, detail="Manila access rule 회수 실패")


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
        _logger.warning("Manila access rule 회수 실패: %s", e)

        raise HTTPException(status_code=502, detail="Manila access rule 회수 실패")
