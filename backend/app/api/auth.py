import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from typing import Optional

from app.models.auth import LoginRequest, TokenResponse, UserInfo, ProjectInfo
from app.services import keystone
from app.services.cache import cached_call

router = APIRouter()


async def _prewarm_dashboard(token: str, project_id: str):
    """로그인 후 백그라운드에서 대시보드 캐시를 미리 워밍."""
    try:
        conn = keystone.get_openstack_connection(token, project_id)
        from app.api.dashboard import _list_servers_as_dicts, _list_flavors_as_dicts
        from app.services import nova, cinder
        await asyncio.gather(
            cached_call(f"union:nova:{project_id}:servers", 15, lambda: _list_servers_as_dicts(conn)),
            cached_call(f"union:nova:{project_id}:limits", 30, lambda: nova.get_project_limits(conn)),
            cached_call(f"union:cinder:{project_id}:limits", 30, lambda: cinder.get_volume_limits(conn)),
            cached_call(f"union:nova:{project_id}:flavors", 300, lambda: _list_flavors_as_dicts(conn)),
        )
    except Exception:
        pass  # best-effort: 실패해도 로그인에는 영향 없음


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, background_tasks: BackgroundTasks):
    try:
        data = keystone.authenticate(
            username=req.username,
            password=req.password,
            project_name=req.project_name,
            domain_name=req.domain_name,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"인증 실패: {e}")

    # 대시보드 캐시 프리워밍 (백그라운드)
    background_tasks.add_task(_prewarm_dashboard, data["token"], data["project_id"])

    return TokenResponse(
        token=data["token"],
        project_id=data["project_id"],
        project_name=data["project_name"],
        user_id=data["user_id"],
        username=data["username"],
        expires_at=data["expires_at"],
    )


@router.get("/me", response_model=UserInfo)
async def me(x_auth_token: Optional[str] = Header(None), x_project_id: Optional[str] = Header(None)):
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="토큰이 필요합니다")
    try:
        data = keystone.validate_token(x_auth_token, project_id=x_project_id or "")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {e}")

    return UserInfo(
        user_id=data["user_id"],
        username=data["username"],
        project_id=data["project_id"],
        project_name=data["project_name"],
        roles=data["roles"],
    )


@router.get("/projects", response_model=list[ProjectInfo])
async def list_projects(x_auth_token: Optional[str] = Header(None)):
    """사용자가 접근 가능한 프로젝트 목록 반환."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="토큰이 필요합니다")
    try:
        projects = keystone.list_projects(x_auth_token)
        return [ProjectInfo(**p) for p in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로젝트 목록 조회 실패: {e}")
