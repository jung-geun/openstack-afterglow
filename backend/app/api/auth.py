from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.models.auth import LoginRequest, TokenResponse, UserInfo, ProjectInfo
from app.services import keystone

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    try:
        data = keystone.authenticate(
            username=req.username,
            password=req.password,
            project_name=req.project_name,
            domain_name=req.domain_name,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"인증 실패: {e}")

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
