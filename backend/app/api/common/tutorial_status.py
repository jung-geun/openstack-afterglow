"""사용자별 튜토리얼(투어) 진행 이력 API.

user_id 는 항상 서버가 token_info 로 계산한다(클라이언트가 보낸 어떤 사용자 식별자도 신뢰하지 않음 — IDOR 방지).
tour_id / status 는 서비스 레이어에서 화이트리스트로 검증한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_token_info
from app.services.tutorial_status import (
    STATUSES,
    TutorialStorageUnavailable,
    TutorialValidationError,
    get_user_statuses,
    set_status,
)

router = APIRouter()


class TutorialStatusResponse(BaseModel):
    # {tour_id: 'completed'|'dismissed'}. 기록이 없는 투어는 키에 없다 → 프론트에서 강조 대상.
    statuses: dict[str, str]


class TutorialStatusPatch(BaseModel):
    status: str


@router.get("/status", response_model=TutorialStatusResponse)
async def get_my_tutorial_statuses(token_info: dict = Depends(get_token_info)):
    """호출자 본인의 튜토리얼 진행 이력 맵을 한 번에 반환한다."""
    statuses = await get_user_statuses(token_info.get("user_id", ""))
    return {"statuses": statuses}


@router.post("/{tour_id}/status", status_code=204)
async def set_my_tutorial_status(
    tour_id: str, payload: TutorialStatusPatch, token_info: dict = Depends(get_token_info)
):
    """본인의 특정 투어 상태를 completed/dismissed 로 기록(upsert)한다."""
    try:
        await set_status(
            user_id=token_info.get("user_id", ""),
            tour_id=tour_id,
            status=payload.status,
        )
    except TutorialValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TutorialStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# 명시적 허용 status 목록을 노출해 프론트/테스트가 참조할 수 있게 한다.
__all__ = ["router", "STATUSES"]
