"""관리자용 프로젝트별 활동 로그 조회 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_token_info, require_admin
from app.services import activity as svc

router = APIRouter()


@router.get("/projects/{project_id}/activity", dependencies=[Depends(require_admin)])
async def list_project_activity(
    project_id: str,
    _: dict = Depends(get_token_info),
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    user_id: str | None = Query(None),
) -> list[dict]:
    """프로젝트 내 모든 사용자 활동 로그 (admin only)."""
    return await svc.list_for_project(
        project_id,
        limit=limit,
        before_id=before_id,
        resource_type=resource_type,
        action=action,
        user_id=user_id,
    )
