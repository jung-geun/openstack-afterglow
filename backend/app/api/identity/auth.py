import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Request
from typing import Optional

from app.models.auth import LoginRequest, TokenResponse, UserInfo, ProjectInfo, GitLabCallbackRequest
from app.services import keystone
from app.services.cache import cached_call
from app.config import get_settings
from app.rate_limit import limiter

router = APIRouter()


async def _prewarm_dashboard(token: str, project_id: str):
    """로그인 후 백그라운드에서 대시보드 캐시를 미리 워밍."""
    try:
        conn = keystone.get_openstack_connection(token, project_id)
        from app.api.common.dashboard import _list_servers_as_dicts, _list_flavors_as_dicts
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
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest, background_tasks: BackgroundTasks):
    try:
        data = keystone.authenticate(
            username=req.username,
            password=req.password,
            project_name=req.project_name,
            domain_name=req.domain_name,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="인증 실패")

    # 대시보드 캐시 프리워밍 (백그라운드)
    background_tasks.add_task(_prewarm_dashboard, data["token"], data["project_id"])

    return TokenResponse(
        token=data["token"],
        project_id=data["project_id"],
        project_name=data["project_name"],
        user_id=data["user_id"],
        username=data["username"],
        expires_at=data["expires_at"],
        roles=data.get("roles", []),
    )


@router.get("/me", response_model=UserInfo)
async def me(x_auth_token: Optional[str] = Header(None), x_project_id: Optional[str] = Header(None)):
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="토큰이 필요합니다")
    try:
        data = keystone.validate_token(x_auth_token, project_id=x_project_id or "")
    except Exception as e:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")

    return UserInfo(
        user_id=data["user_id"],
        username=data["username"],
        project_id=data["project_id"],
        project_name=data["project_name"],
        roles=data["roles"],
    )


@router.get("/session-info")
async def session_info(x_auth_token: Optional[str] = Header(None), x_project_id: Optional[str] = Header(None)):
    """현재 세션의 남은 시간(초)과 설정된 타임아웃을 반환."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="토큰이 필요합니다")
    from app.api.deps import get_session_remaining
    settings = get_settings()
    remaining = await get_session_remaining(x_auth_token, x_project_id or "")
    return {
        "remaining_seconds": remaining,
        "timeout_seconds": settings.session_timeout_seconds,
        "warning_before_seconds": settings.session_warning_before_seconds,
    }


@router.post("/extend-session")
async def extend_session_endpoint(x_auth_token: Optional[str] = Header(None), x_project_id: Optional[str] = Header(None)):
    """세션을 연장 (시작 시간을 지금으로 재설정)."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="토큰이 필요합니다")
    try:
        # Keystone 토큰 여전히 유효한지 확인
        keystone.validate_token(x_auth_token, project_id=x_project_id or "")
    except Exception as e:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
    from app.api.deps import extend_session
    await extend_session(x_auth_token, x_project_id or "")
    settings = get_settings()
    return {"message": "세션이 연장되었습니다", "timeout_seconds": settings.session_timeout_seconds}


@router.get("/projects", response_model=list[ProjectInfo])
async def list_projects(x_auth_token: Optional[str] = Header(None)):
    """사용자가 접근 가능한 프로젝트 목록 반환."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="토큰이 필요합니다")
    try:
        projects = keystone.list_projects(x_auth_token)
        return [ProjectInfo(**p) for p in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail="프로젝트 목록 조회 실패")


@router.get("/gitlab/enabled")
async def gitlab_enabled():
    """GitLab OIDC 활성화 여부 반환 (프론트엔드에서 버튼 표시 여부 결정)."""
    settings = get_settings()
    return {"enabled": settings.gitlab_oidc_enabled}


@router.get("/gitlab/authorize")
async def gitlab_authorize():
    """GitLab OAuth2 인증 URL 반환."""
    settings = get_settings()
    if not settings.gitlab_oidc_enabled:
        raise HTTPException(status_code=404, detail="GitLab OIDC가 비활성화 상태입니다")
    from app.services.gitlab_oidc import get_authorize_url
    try:
        url = await get_authorize_url()
    except Exception as e:
        raise HTTPException(status_code=500, detail="GitLab 인증 URL 생성 실패")
    return {"authorize_url": url}


@router.post("/gitlab/callback", response_model=TokenResponse)
@limiter.limit("10/minute")
async def gitlab_callback(request: Request, req: GitLabCallbackRequest, background_tasks: BackgroundTasks):
    """GitLab OAuth2 콜백: authorization code로 Keystone 토큰 발급."""
    settings = get_settings()
    if not settings.gitlab_oidc_enabled:
        raise HTTPException(status_code=404, detail="GitLab OIDC가 비활성화 상태입니다")
    from app.services.gitlab_oidc import exchange_code
    try:
        data = await exchange_code(req.code, req.state)
    except Exception as e:
        raise HTTPException(status_code=401, detail="GitLab 인증 실패")

    background_tasks.add_task(_prewarm_dashboard, data["token"], data["project_id"])

    return TokenResponse(
        token=data["token"],
        project_id=data["project_id"],
        project_name=data["project_name"],
        user_id=data["user_id"],
        username=data["username"],
        expires_at=data["expires_at"],
        roles=data.get("roles", []),
    )
