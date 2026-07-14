"""기존 LibreChat 인스턴스 MongoDB 읽기 전용 클라이언트.

Afterglow는 이 MongoDB에 쓰기를 수행하지 않는다. LibreChat 스키마(users/transactions
컬렉션)에 결합되므로, LibreChat 버전 업으로 필드가 바뀌면 이 모듈만 갱신하면 되도록
조회 로직을 여기에 얇게 모아둔다.
"""

import logging
import re

from app.config import get_settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """motor AsyncIOMotorClient를 lazy 초기화해 반환. mongo_url 미설정 시 None."""
    global _client
    settings = get_settings()
    if not settings.librechat_mongo_url:
        return None
    if _client is None:
        from motor.motor_asyncio import AsyncIOMotorClient

        _client = AsyncIOMotorClient(settings.librechat_mongo_url)
    return _client


async def get_usage_for_username(username: str) -> dict | None:
    """LibreChat username(대소문자 무시)으로 사용자를 찾아 토큰 사용량을 집계.

    반환: {"total_raw_amount": float, "total_token_value": float, "transaction_count": int}
    또는 사용자를 찾지 못하면 None. Mongo 미설정/조회 실패 시에도 None(fail-open, 항상 200).
    """
    client = _get_client()
    if client is None:
        return None

    try:
        db = client.get_default_database()
        # username은 외부(Keystone) 신뢰 불가 입력 — 정규식 메타문자로 다른 사용자와
        # 매칭되는 것을 막기 위해 반드시 re.escape로 리터럴화한다.
        escaped = re.escape(username)
        user_doc = await db["users"].find_one({"username": {"$regex": f"^{escaped}$", "$options": "i"}})
        if not user_doc:
            return None

        pipeline = [
            {"$match": {"user": user_doc["_id"]}},
            {
                "$group": {
                    "_id": None,
                    "total_raw_amount": {"$sum": "$rawAmount"},
                    "total_token_value": {"$sum": "$tokenValue"},
                    "transaction_count": {"$sum": 1},
                }
            },
        ]
        result = await db["transactions"].aggregate(pipeline).to_list(length=1)
        if not result:
            return {"total_raw_amount": 0.0, "total_token_value": 0.0, "transaction_count": 0}

        row = result[0]
        return {
            "total_raw_amount": float(row.get("total_raw_amount", 0.0)),
            "total_token_value": float(row.get("total_token_value", 0.0)),
            "transaction_count": int(row.get("transaction_count", 0)),
        }
    except Exception:
        logger.warning("LibreChat MongoDB 사용량 조회 실패", exc_info=True)
        return None
