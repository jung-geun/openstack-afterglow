import asyncio
import hashlib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from typing import Optional

from app.models.auth import LoginRequest, TokenResponse, UserInfo, ProjectInfo, GitLabCallbackRequest
from app.services import keystone
from app.services.cache import cached_call, ttl_fast, ttl_normal, ttl_static
from app.config import get_settings
from app.rate_limit import limiter
from app.api.deps import get_token_info, get_session_remaining, extend_session

router = APIRouter()


async def _prewarm_dashboard(token: str, project_id: str):
    """로그인 후 백그라운드에서 대시보드 캐시를 미리 워밍."""
    try:
        conn = keystone.get_openstack_connection(token, project_id)
        from app.api.common.dashboard import _list_servers_as_dicts, _list_flavors_as_dicts
        from app.services import nova, cinder
        await asyncio.gather(
            cached_call(f"union:nova:{project_id}:servers", ttl_fast(), lambda: _list_servers_as_dicts(conn)),
            cached_call(f"union:nova:{project_id}:limits", ttl_normal(), lambda: nova.get_project_limits(conn)),
            cached_call(f"union:cinder:{project_id}:limits", ttl_normal(), lambda: cinder.get_volume_limits(conn)),
            cached_call(f"union:nova:{project_id}:flavors", ttl_static(), lambda: _list_flavors_as_dicts(conn)),
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

    # 사용자의 default_project_id 조회
    default_project_id = ""
    try:
        conn = keystone.get_openstack_connection(data["token"], data["project_id"])
        u = conn.identity.get_user(data["user_id"])
        default_project_id = getattr(u, "default_project_id", None) or ""
    except Exception:
        pass

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
        default_project_id=default_project_id,
    )


@router.get("/me", response_model=UserInfo)
async def me(token_info: dict = Depends(get_token_info)):
    return UserInfo(
        user_id=token_info["user_id"],
        username=token_info["username"],
        project_id=token_info["project_id"],
        project_name=token_info["project_name"],
        roles=token_info["roles"],
    )


@router.get("/session-info")
async def session_info(token_info: dict = Depends(get_token_info)):
    """현재 세션의 남은 시간(초)과 설정된 타임아웃을 반환."""
    settings = get_settings()
    remaining = await get_session_remaining(token_info["token"], token_info["project_id"])
    return {
        "remaining_seconds": remaining,
        "timeout_seconds": settings.session_timeout_seconds,
        "warning_before_seconds": settings.session_warning_before_seconds,
    }


@router.post("/extend-session")
async def extend_session_endpoint(token_info: dict = Depends(get_token_info)):
    """세션을 연장 (시작 시간을 지금으로 재설정)."""
    await extend_session(token_info["token"], token_info["project_id"])
    settings = get_settings()
    return {"message": "세션이 연장되었습니다", "timeout_seconds": settings.session_timeout_seconds}


@router.post("/logout")
async def logout(token_info: dict = Depends(get_token_info)):
    """로그아웃: Redis 세션 삭제 및 Keystone 토큰 폐기."""
    from app.services.cache import _get_redis
    token = token_info["token"]
    pid = token_info.get("project_id") or "noscope"
    h = hashlib.sha256(token.encode()).hexdigest()[:32]
    try:
        r = await _get_redis()
        await r.delete(f"union:session:{h}:{pid}", f"union:session-abs:{h}:{pid}")
    except Exception:
        pass
    try:
        await asyncio.to_thread(keystone.revoke_token, token)
    except Exception:
        pass
    return {"message": "로그아웃 완료"}


@router.get("/projects", response_model=list[ProjectInfo])
async def list_projects(token_info: dict = Depends(get_token_info)):
    """사용자가 접근 가능한 프로젝트 목록 반환."""
    try:
        projects = keystone.list_projects(token_info["token"])
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

    # 사용자의 default_project_id 조회
    gl_default_project_id = ""
    try:
        gl_conn = keystone.get_openstack_connection(data["token"], data["project_id"])
        gl_u = gl_conn.identity.get_user(data["user_id"])
        gl_default_project_id = getattr(gl_u, "default_project_id", None) or ""
    except Exception:
        pass

    background_tasks.add_task(_prewarm_dashboard, data["token"], data["project_id"])

    return TokenResponse(
        token=data["token"],
        project_id=data["project_id"],
        project_name=data["project_name"],
        user_id=data["user_id"],
        username=data["username"],
        expires_at=data["expires_at"],
        roles=data.get("roles", []),
        default_project_id=gl_default_project_id,
    )
