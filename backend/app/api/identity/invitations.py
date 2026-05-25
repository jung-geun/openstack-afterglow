"""프로젝트 초대 수락/거절 공개 API."""

import logging

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_token_info
from app.database import get_session

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.get("/{token}")
async def get_invitation_info(
    token: str = Path(...),
    session: AsyncSession = Depends(get_session),
):
    """초대 링크 정보 조회 (인증 불필요). 초대 수락 페이지에서 호출."""
    from app.services.project_service import get_invitation_info
    return await get_invitation_info(token, session)


@router.post("/{token}/accept")
async def accept_invitation(
    token: str = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """초대 수락. JWT 인증 필수 + 수락자 이메일 == invited_email 검증."""
    from app.services.project_service import accept_invitation

    accepting_email = await _get_user_email(token_info["user_id"])
    return await accept_invitation(
        plaintext_token=token,
        accepting_user_id=token_info["user_id"],
        accepting_email=accepting_email,
        session=session,
    )


@router.post("/{token}/decline", status_code=200)
async def decline_invitation(
    token: str = Path(...),
    session: AsyncSession = Depends(get_session),
):
    """초대 거절 (인증 불필요 — 토큰만으로 처리)."""
    from app.services.project_service import decline_invitation
    return await decline_invitation(token, session)


async def _get_user_email(user_id: str) -> str:
    """Keystone에서 사용자 이메일 조회."""
    import asyncio
    from app.services import keystone

    def _lookup():
        ks = keystone._get_admin_ks_client()
        try:
            u = ks.users.get(user_id)
            return getattr(u, "email", "") or ""
        except Exception:
            return ""

    try:
        return await asyncio.to_thread(_lookup)
    except Exception:
        return ""
