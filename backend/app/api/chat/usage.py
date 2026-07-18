"""빌트인 AI 채팅 사용량 조회 엔드포인트.

로그인 사용자 본인의 누적 사용량(크레딧·토큰·요청 수)을 chat_usage_logs 원장에서 집계한다.
(구 LibreChat MongoDB 미러링을 대체 — LibreChat 의존성 제거.)
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_token_info
from app.services.chat.usage import user_usage_summary

router = APIRouter()


@router.get("/usage")
async def get_chat_usage(token_info: dict = Depends(get_token_info)):
    """로그인 사용자 본인의 빌트인 채팅 사용량 요약. 데이터/DB 없으면 found=False 로 200 반환."""
    return await user_usage_summary(token_info.get("user_id", ""), token_info.get("project_id", ""))
