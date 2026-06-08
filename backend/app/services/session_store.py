"""Refresh JTI → {keystone_token, project_id, user_id, exp} Redis 세션 저장소.

키 스킴: afterglow:refresh:{jti}
TTL: refresh JWT 만료까지 남은 초 (exp - now)

access JWT의 rjti 필드가 이 키를 가리킨다.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from app.services.cache import _get_redis

_PREFIX = "afterglow:refresh:"
_USER_INDEX_PREFIX = "afterglow:user-sessions:"
_TOUCH_THROTTLE_SECONDS = 60  # last_ip/fp 갱신 최소 간격 (Redis 쓰기 폭증 방지)
_SENSITIVE_KEYS = {"keystone_token"}  # list_user_sessions에서 제거할 민감 필드

_logger = logging.getLogger(__name__)


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
    origin_ip: str = "",
    origin_fp: str = "",
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
            # 출처 바인딩 필드 (최초 로그인 시 설정, 회전 너머 그대로 운반)
            "origin_ip": origin_ip,
            "origin_fp": origin_fp,
            # 마지막 사용 위치 (매 요청마다 쓰로틀 갱신)
            "last_ip": origin_ip,
            "last_fp": origin_fp,
            "last_seen": now,
            # 블랙리스트 (출처 불일치 자동 차단 또는 수동 플래그)
            "blacklisted": False,
            "blacklist_reason": "",
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


async def revoke_user_sessions(user_id: str, *, revoke_keystone: bool = True) -> int:
    """사용자의 모든 refresh 세션을 즉시 삭제.

    revoke_keystone=True(기본)이면 각 세션의 Keystone 토큰도 폐기한다
    (DELETE /v3/auth/tokens). best-effort — 개별 실패는 warning 후 계속.

    admin role 박탈, 전체 로그아웃 등 강제 로그아웃 시 호출.

    Returns:
        삭제된 세션 수
    """
    r = await _get_redis()
    index_key = _user_index_key(user_id)
    raw_jtis = await r.smembers(index_key)
    if not raw_jtis:
        return 0
    jtis = [j.decode() if isinstance(j, bytes) else j for j in raw_jtis]

    # Keystone 직접 폐기 (삭제 전에 토큰 수집)
    if revoke_keystone:
        from app.services import keystone  # 순환 임포트 방지용 지연 임포트

        ks_tokens: list[str] = []
        for jti in jtis:
            raw = await r.get(_key(jti))
            if raw:
                try:
                    sess = json.loads(raw)
                    tok = sess.get("keystone_token", "")
                    if tok:
                        ks_tokens.append(tok)
                except Exception:
                    pass

        # 각 Keystone 토큰 폐기 (best-effort — 실패해도 Redis 삭제는 진행)
        for tok in ks_tokens:
            try:
                await asyncio.to_thread(keystone.revoke_token, tok)
            except Exception:
                _logger.warning(
                    "revoke_user_sessions: Keystone revoke 실패 (user_id=%s)", user_id, exc_info=True
                )

    keys = [_key(jti) for jti in jtis] + [index_key]
    await r.delete(*keys)
    return len(jtis)


async def blacklist_session(jti: str, reason: str = "") -> None:
    """세션을 블랙리스트에 등록. 이후 인증 게이트에서 즉시 차단된다.

    TTL은 기존 값 유지 — 세션이 만료되면 자동 제거.
    이미 삭제된 세션이면 no-op.
    """
    r = await _get_redis()
    key = _key(jti)
    raw = await r.get(key)
    if raw is None:
        return
    sess = json.loads(raw)
    sess["blacklisted"] = True
    sess["blacklist_reason"] = reason
    ttl = await r.ttl(key)
    if ttl > 0:
        await r.setex(key, ttl, json.dumps(sess))
    elif ttl == -1:
        # TTL 없는 영구 키(비정상) — 그냥 덮어씀
        await r.set(key, json.dumps(sess))


async def touch_session_seen(jti: str, ip: str, fp: str) -> None:
    """last_ip / last_fp / last_seen 갱신 (마지막 사용 위치 추적).

    쓰로틀: ip·fp가 동일하고 last_seen이 60초 이내면 스킵 (Redis 쓰기 폭증 방지).
    기존 update_session_token 패턴을 따른다.
    """
    r = await _get_redis()
    key = _key(jti)
    raw = await r.get(key)
    if raw is None:
        return
    sess = json.loads(raw)
    now = int(datetime.now(UTC).timestamp())
    # 쓰로틀: 같은 IP/지문이고 최근 갱신이 60초 이내면 skip
    if (
        sess.get("last_ip") == ip
        and sess.get("last_fp") == fp
        and now - sess.get("last_seen", 0) < _TOUCH_THROTTLE_SECONDS
    ):
        return
    sess["last_ip"] = ip
    sess["last_fp"] = fp
    sess["last_seen"] = now
    ttl = await r.ttl(key)
    if ttl > 0:
        await r.setex(key, ttl, json.dumps(sess))


async def list_user_sessions(user_id: str) -> list[dict]:
    """사용자의 활성 세션 목록 반환 (keystone_token 등 민감 필드 제거).

    user-index SET + 각 세션 JSON 조회. 만료된 스테일 항목은 인덱스에서 정리.
    셀프서비스 (/api/auth/sessions) 및 관리자 (/api/admin/users/{id}/sessions) 공용.
    """
    r = await _get_redis()
    index_key = _user_index_key(user_id)
    raw_jtis = await r.smembers(index_key)
    if not raw_jtis:
        return []
    jtis = [j.decode() if isinstance(j, bytes) else j for j in raw_jtis]
    sessions: list[dict] = []
    stale: list[str] = []
    for jti in jtis:
        raw = await r.get(_key(jti))
        if raw is None:
            stale.append(jti)
            continue
        try:
            sess = json.loads(raw)
            safe = {k: v for k, v in sess.items() if k not in _SENSITIVE_KEYS}
            safe["jti"] = jti
            sessions.append(safe)
        except Exception:
            stale.append(jti)
    # 스테일 인덱스 정리 (fire-and-forget)
    if stale:
        try:
            await r.srem(index_key, *stale)
        except Exception:
            pass
    return sessions
