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
_USER_INDEX_PREFIX = "afterglow:user-sessions:"


def _key(jti: str) -> str:
    return f"{_PREFIX}{jti}"


def _user_index_key(user_id: str) -> str:
    return f"{_USER_INDEX_PREFIX}{user_id}"


async def store_session(
    jti: str,
    keystone_token: str,
    project_id: str,
    user_id: str,
    exp: int,
    auth_method: str = "password",
) -> None:
    """refresh JTI에 세션 데이터를 저장. TTL은 refresh 만료 시각까지."""
    r = await _get_redis()
    now = int(datetime.now(UTC).timestamp())
    ttl = max(exp - now, 1)
    data = json.dumps(
        {
            "keystone_token": keystone_token,
            "project_id": project_id,
            "user_id": user_id,
            "exp": exp,
            "auth_method": auth_method,
        }
    )
    async with r.pipeline() as pipe:
        pipe.setex(_key(jti), ttl, data)
        pipe.sadd(_user_index_key(user_id), jti)
        pipe.expire(_user_index_key(user_id), ttl)
        await pipe.execute()


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
    raw = await r.get(_key(jti))
    if raw:
        try:
            sess = json.loads(raw)
            uid = sess.get("user_id", "")
            if uid:
                await r.srem(_user_index_key(uid), jti)
        except Exception:
            pass
    await r.delete(_key(jti))


async def update_session_token(jti: str, new_keystone_token: str) -> None:
    """세션의 keystone_token을 새 토큰으로 갱신. TTL은 기존 값 유지.

    validate_token이 POST /v3/auth/tokens으로 새 Keystone 토큰을 발급할 때 호출.
    원본 토큰이 만료되기 전에 세션을 갱신해 1시간 TTL 문제를 방지.
    """
    r = await _get_redis()
    key = _key(jti)
    raw = await r.get(key)
    if raw is None:
        return
    sess = json.loads(raw)
    if sess.get("keystone_token") == new_keystone_token:
        return
    sess["keystone_token"] = new_keystone_token
    ttl = await r.ttl(key)
    if ttl > 0:
        await r.setex(key, ttl, json.dumps(sess))


async def revoke_user_sessions(user_id: str) -> int:
    """사용자의 모든 refresh 세션을 즉시 삭제. admin role 박탈 등 강제 로그아웃 시 호출.

    Returns:
        삭제된 세션 수
    """
    r = await _get_redis()
    index_key = _user_index_key(user_id)
    raw_jtis = await r.smembers(index_key)
    if not raw_jtis:
        return 0
    jtis = [j.decode() if isinstance(j, bytes) else j for j in raw_jtis]
    keys = [_key(jti) for jti in jtis] + [index_key]
    await r.delete(*keys)
    return len(jtis)
