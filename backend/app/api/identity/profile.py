"""사용자 본인 프로필 관리 엔드포인트."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_token_info, get_os_conn
from app.services import keystone
from app.config import get_settings

_logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    description: str | None = None
    default_project_id: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.get("")
async def get_profile(
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """본인 프로필 조회."""
    user_id = token_info["user_id"]

    def _get():
        try:
            u = conn.identity.get_user(user_id)
            return {
                "id": u.id,
                "name": u.name or "",
                "email": getattr(u, "email", None) or "",
                "description": getattr(u, "description", None) or "",
                "default_project_id": getattr(u, "default_project_id", None) or "",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail="프로필 조회 실패")

    try:
        return await asyncio.to_thread(_get)
    except HTTPException:
        raise


@router.patch("")
async def update_profile(
    req: UpdateProfileRequest,
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """본인 프로필 수정 (이메일, 설명, 이름)."""
    user_id = token_info["user_id"]

    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.email is not None:
            kwargs["email"] = req.email
        if req.description is not None:
            kwargs["description"] = req.description
        if req.default_project_id is not None:
            kwargs["default_project_id"] = req.default_project_id
        if not kwargs:
            raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")
        try:
            u = conn.identity.update_user(user_id, **kwargs)
            return {
                "id": u.id,
                "name": u.name or "",
                "email": getattr(u, "email", None) or "",
                "description": getattr(u, "description", None) or "",
                "default_project_id": getattr(u, "default_project_id", None) or "",
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"프로필 수정 실패: {e}")

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


@router.post("/password")
async def change_password(
    req: ChangePasswordRequest,
    token_info: dict = Depends(get_token_info),
    conn=Depends(get_os_conn),
):
    """패스워드 변경 (현재 패스워드 검증 후 변경)."""
    user_id = token_info["user_id"]
    username = token_info["username"]
    project_name = token_info.get("project_name", "")

    # 현재 패스워드 검증
    try:
        keystone.authenticate(username, req.current_password, project_name)
    except Exception:
        raise HTTPException(status_code=401, detail="현재 패스워드가 올바르지 않습니다")

    def _change():
        try:
            conn.identity.update_user(user_id, password=req.new_password)
            return {"status": "changed"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"패스워드 변경 실패: {e}")

    try:
        return await asyncio.to_thread(_change)
    except HTTPException:
        raise
