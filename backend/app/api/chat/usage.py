"""LibreChat 토큰 사용량 읽기 전용 미러링 엔드포인트.

기존에 운영 중인 LibreChat 인스턴스의 MongoDB를 조회해 현재 로그인 사용자 본인의
토큰 사용량만 노출한다. Afterglow는 이 데이터에 쓰기를 수행하지 않는다.

신원 조인: Afterglow token_info의 username(Keystone, GitLab federation 매핑)을
LibreChat username과 매칭한다. 두 시스템 사용자명이 어긋나면 조회 실패로 취급한다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_token_info
from app.services.librechat_mongo import get_usage_for_username

router = APIRouter()


@router.get("/usage")
async def get_chat_usage(token_info: dict = Depends(get_token_info)):
    """로그인 사용자 본인의 LibreChat 토큰 사용량 집계.

    LibreChat 미설정이거나 매칭되는 사용자가 없으면 found=False로 200 반환
    (Grafana 대시보드 엔드포인트와 동일하게 항상 200 — 프론트엔드가 빈 상태로 판단).
    """
    username = token_info.get("username", "")
    usage = await get_usage_for_username(username) if username else None

    if usage is None:
        return {"found": False, "total_raw_amount": 0.0, "total_token_value": 0.0, "transaction_count": 0}

    return {"found": True, **usage}
