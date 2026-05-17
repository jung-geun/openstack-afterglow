"""Refresh JTI → {keystone_token, project_id, user_id, exp} Redis 세션 저장소.

키 스킴: afterglow:refresh:{jti}
TTL: refresh JWT 만료까지 남은 초 (exp - now)

access JWT의 rjti 필드가 이 키를 가리킨다.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.services.cache import _get_redis

_PREFIX = "afterglow:refresh:"


def _key(jti: str) -> str:
    return f"{_PREFIX}{jti}"


async def store_session(
    jti: str,
    keystone_token: str,
    project_id: str,
    user_id: str,
    exp: int,
) -> None:
    """refresh JTI에 세션 데이터를 저장. TTL은 refresh 만료 시각까지."""
    r = await _get_redis()
    now = int(datetime.now(UTC).timestamp())
    ttl = max(exp - now, 1)
    data = json.dumps({
        "keystone_token": keystone_token,
        "project_id": project_id,
        "user_id": user_id,
        "exp": exp,
    })
    await r.setex(_key(jti), ttl, data)


async def get_session(jti: str) -> dict | None:
    """refresh JTI로 세션 데이터 조회. 없으면 None."""
    r = await _get_redis()
    raw = await r.get(_key(jti))
    if raw is None:
        return None
    return json.loads(raw)


async def delete_session(jti: str) -> None:
    """refresh JTI 세션 삭제. 로그아웃·토큰 회전 시 호출."""
    r = await _get_redis()
    await r.delete(_key(jti))
