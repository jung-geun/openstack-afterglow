"""빌트인 AI 채팅 관리자 통계 — 전 엔드포인트 require_admin, GET 전용(조회).

전체 시스템(+프로젝트 필터)의 사용량을 사용자별·모델별·월별·전체로 집계해 대시보드에 제공한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.services.chat import stats as stats_service

router = APIRouter(dependencies=[Depends(require_admin)])

_RANGES = ("30d", "90d", "1y", "all")


def _norm_range(value: str) -> str:
    return value if value in _RANGES else "all"


@router.get("/admin/stats")
async def get_stats(
    range: str = Query(default="all"),
    project_id: str | None = Query(default=None),
    user_limit: int = Query(default=20, ge=1, le=200),
):
    """대시보드 초기 로드 — overview + by_model + monthly + by_user(top-N) + 프로젝트 목록."""
    rng = _norm_range(range)
    pid = project_id or None
    return {
        "range": rng,
        "project_id": pid,
        "overview": await stats_service.overview(rng, pid),
        "by_model": await stats_service.by_model(rng, pid),
        "monthly": await stats_service.monthly(rng, pid),
        "by_user": await stats_service.by_user(rng, pid, limit=user_limit),
        "projects": await stats_service.projects_with_usage(rng),
    }


@router.get("/admin/stats/users")
async def get_stats_users(
    range: str = Query(default="all"),
    project_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """사용자별 집계 페이지네이션(표 더보기)."""
    rng = _norm_range(range)
    return {"users": await stats_service.by_user(rng, project_id or None, limit=limit, offset=offset)}
