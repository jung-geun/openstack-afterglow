"""사용자 공지 수신/읽음 API.

타겟팅 판별은 항상 서버가 token_info(user_id/project_id)로 계산한다.
클라이언트가 보낸 어떤 타겟 파라미터도 존재하지 않으며, 존재해서도 안 된다 — IDOR 방지.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_token_info
from app.services.announcements import (
    AnnouncementStorageUnavailable,
    count_unread,
    list_user_announcements,
    mark_read,
)

router = APIRouter()


class AnnouncementUserResponse(BaseModel):
    id: int
    created_at: str
    title: str
    body: str
    severity: str
    is_read: bool


class UnreadCountResponse(BaseModel):
    unread_count: int


@router.get("", response_model=list[AnnouncementUserResponse])
async def get_my_announcements(token_info: dict = Depends(get_token_info)):
    """호출자에게 타겟된 활성 공지만 반환 (전체 / 본인 프로젝트 / 본인 유저)."""
    return await list_user_announcements(
        user_id=token_info.get("user_id", ""),
        project_id=token_info.get("project_id", ""),
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(token_info: dict = Depends(get_token_info)):
    unread = await count_unread(
        user_id=token_info.get("user_id", ""),
        project_id=token_info.get("project_id", ""),
    )
    return {"unread_count": unread}


@router.post("/{announcement_id}/read", status_code=204)
async def mark_announcement_read(announcement_id: int, token_info: dict = Depends(get_token_info)):
    """읽음 처리 전 타겟팅을 서버에서 재검증한다.

    다른 유저/프로젝트 대상 공지에 대한 read-mark를 차단하기 위해, 존재하되
    호출자에게 타겟되지 않은 공지는 (구분되지 않게) 404로 응답한다.
    """
    try:
        found = await mark_read(
            announcement_id=announcement_id,
            user_id=token_info.get("user_id", ""),
            project_id=token_info.get("project_id", ""),
        )
    except AnnouncementStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=404, detail="공지를 찾을 수 없습니다")
