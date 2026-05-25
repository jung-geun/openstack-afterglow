from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, Query

from app.config import get_settings
from app.services import keystone
from app.services.cache import cached_call, invalidate

if TYPE_CHECKING:
    import openstack

_logger = logging.getLogger(__name__)

# 토큰 검증 결과 캐시 TTL — Keystone revoke / logout 후 공격자에게 노출되는 window 를
# 60초로 제한. 이전엔 ttl_static() (300s) 였음.
_TOKEN_CACHE_TTL = 60


def _session_key(token_hash: str, project_id: str) -> str:
    return f"afterglow:session_start:{token_hash}:{project_id or 'noscope'}"


def _validate_cache_key(token_hash: str, project_id: str) -> str:
    return f"afterglow:session:{token_hash}:{project_id or 'noscope'}"


async def _cached_validate(token: str, project_id: str) -> dict:
    """토큰 검증 결과를 Redis에 짧게 캐시 (TTL 60s). logout/revoke 시 invalidate."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cache_key = _validate_cache_key(token_hash, project_id)
    return await cached_call(cache_key, _TOKEN_CACHE_TTL, lambda: keystone.validate_token(token, project_id=project_id))


async def invalidate_token_cache(token: str, project_id: str | None) -> None:
    """logout / revoke 직후 호출 — 검증 캐시 + 세션 시작/절대 키를 모두 삭제.

    Redis 장애 시 silent fail (logout 흐름을 막지 않음).
    """
    pid = project_id or "noscope"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    keys = [
        _validate_cache_key(token_hash, pid),
        _session_key(token_hash, pid),
        f"afterglow:session-abs:{token_hash}:{pid}",
    ]
    for key in keys:
        try:
            await invalidate(key)
        except Exception:
            _logger.warning("토큰 캐시 invalidate 실패 (%s)", key, exc_info=True)


async def _check_session_timeout(token_hash: str, project_id: str) -> None:
    """세션 시작 시간이 없으면 기록하고, 있으면 타임아웃 여부를 체크."""
    from app.services.cache import _get_redis  # 지연 임포트

    settings = get_settings()
    timeout = settings.session_timeout_seconds
    key = _session_key(token_hash, project_id)
    try:
        r = await _get_redis()
        start_bytes = await r.get(key)
        now = time.time()
        if start_bytes is None:
            # 첫 요청 — 세션 시작 시간 기록 (TTL = timeout + 여유 60s)
            await r.setex(key, timeout + 60, str(now))
        else:
            start = float(start_bytes)
            if now - start > timeout:
                await r.delete(key)
                raise HTTPException(status_code=401, detail="세션이 만료되었습니다. 다시 로그인해 주세요.")
    except HTTPException:
        raise
    except Exception:
        # fail-closed: Redis 장애 시 세션 검증 불가 → 요청 거부
        # 401을 반환: 세션 유효성을 확인할 수 없으면 인증되지 않은 것으로 처리
        _logger.error("Redis 장애로 세션 타임아웃 검증 불가 — 요청 거부 (fail-closed)", exc_info=True)
        raise HTTPException(status_code=401, detail="세션 유효성을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.")


async def get_session_remaining(token: str, project_id: str) -> int:
    """세션 남은 시간(초) 반환. Redis 오류 시 -1."""
    from app.services.cache import _get_redis

    settings = get_settings()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    key = _session_key(token_hash, project_id or "noscope")
    try:
        r = await _get_redis()
        start_bytes = await r.get(key)
        if start_bytes is None:
            return settings.session_timeout_seconds
        elapsed = time.time() - float(start_bytes)
        remaining = int(settings.session_timeout_seconds - elapsed)
        return max(0, remaining)
    except Exception:
        return -1


async def extend_session(token: str, project_id: str) -> None:
    """세션 시작 시간을 지금으로 재설정 (연장). 절대 만료 시간 초과 시 HTTPException 발생."""
    from app.services.cache import _get_redis

    settings = get_settings()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    key = _session_key(token_hash, project_id or "noscope")
    abs_key = f"afterglow:session-abs:{token_hash}:{project_id or 'noscope'}"
    try:
        r = await _get_redis()
        now = time.time()
        # 절대 만료 확인
        abs_start_bytes = await r.get(abs_key)
        if abs_start_bytes is not None:
            if now - float(abs_start_bytes) > settings.session_absolute_timeout:
                await r.delete(key)
                await r.delete(abs_key)
                raise HTTPException(status_code=401, detail="세션 최대 시간을 초과했습니다. 다시 로그인해 주세요.")
        else:
            # 절대 시작 시각 최초 기록
            await r.setex(abs_key, settings.session_absolute_timeout + 60, str(now))
        await r.setex(key, settings.session_timeout_seconds + 60, str(now))
    except HTTPException:
        raise
    except Exception:
        _logger.warning("Redis 장애로 세션 연장을 건너뜁니다", exc_info=True)


async def _resolve_jwt_token_info(bearer_token: str, x_project_id: str | None) -> dict:
    """Bearer access JWT 검증 → Redis 세션 조회 → token_info dict 반환.

    x_project_id가 JWT의 project_id와 다르면 Keystone rescope (프로젝트 전환용).
    """
    from app.services import jwt_service
    from app.services.session_store import get_session

    try:
        payload = jwt_service.verify_access(bearer_token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 액세스 토큰")

    refresh_jti = payload.get("rjti")
    if not refresh_jti:
        raise HTTPException(status_code=401, detail="액세스 토큰 형식 오류")

    sess = await get_session(refresh_jti)
    if sess is None:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다. 다시 로그인해 주세요.")

    jwt_project_id = payload.get("project_id", "")
    target_project_id = x_project_id or jwt_project_id

    # 권한 정보는 항상 Keystone live 검증(60s 캐시). JWT payload에서 꺼내지 않는다.
    # 프로젝트 전환 여부와 무관하게 동일 경로로 통합 — stale window 제거.
    effective_project_id = target_project_id or sess.get("project_id", jwt_project_id)
    info = await _cached_validate(sess["keystone_token"], effective_project_id)

    # X-Project-Id로 실제 rescope가 발생한 경우에만 접근 기록 (fire-and-forget)
    user_id_for_record = info.get("user_id", payload.get("sub", ""))
    if x_project_id and x_project_id != jwt_project_id and user_id_for_record:
        from app.services.recent_projects import record_project_access

        asyncio.create_task(record_project_access(user_id_for_record, x_project_id))

    return {
        "token": info["token"],
        "user_id": info.get("user_id", payload.get("sub", "")),
        "username": info.get("username", payload.get("username", "")),
        "project_id": info.get("project_id", effective_project_id),
        "project_name": info.get("project_name", payload.get("project_name", "")),
        "roles": info.get("roles", []),
        "is_system_admin": info.get("is_system_admin", False),
        "refresh_jti": refresh_jti,
    }


async def get_token_info(
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None),
    x_project_id: str | None = Header(None),
) -> dict:
    """모든 인증 필요 엔드포인트에서 사용하는 Depends 함수.

    우선순위:
    1. Authorization: Bearer <access_jwt>  — JWT 경로 (신규)
    2. X-Auth-Token: <keystone_token>      — 레거시 경로 (하위호환)
    """
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization[7:]
        return await _resolve_jwt_token_info(bearer, x_project_id)

    if not x_auth_token:
        raise HTTPException(status_code=401, detail="인증 헤더가 필요합니다")
    try:
        token_hash = hashlib.sha256(x_auth_token.encode()).hexdigest()
        await _check_session_timeout(token_hash, x_project_id or "")
        return await _cached_validate(x_auth_token, x_project_id or "")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")


def require_admin(token_info: dict = Depends(get_token_info)):
    """시스템 관리자(admin 프로젝트의 admin role 보유자)가 아니면 403 반환."""
    if not token_info.get("is_system_admin", False):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")


async def require_project_manager(
    project_id: str,
    token_info: dict = Depends(get_token_info),
) -> dict:
    """현재 프로젝트의 manager가 아니면 403. system admin은 bypass.

    엔드포인트에서 Path 파라미터로 project_id를 직접 전달받아 사용:
        manager = await require_project_manager(project_id, token_info=Depends(get_token_info))
    또는 헬퍼 함수로 직접 호출:
        await check_project_manager(project_id, token_info, session)
    """
    if token_info.get("is_system_admin", False):
        return token_info

    from app.database import get_session_factory
    from app.services.project_service import is_project_manager

    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="DB를 사용할 수 없습니다")

    async with factory() as session:
        if not await is_project_manager(project_id, token_info["user_id"], session):
            raise HTTPException(status_code=403, detail="프로젝트 관리자 권한이 필요합니다")

    return token_info


async def get_os_conn(
    authorization: str | None = Header(None),
    x_auth_token: str | None = Header(None),
    x_project_id: str | None = Header(None),
) -> AsyncGenerator[openstack.connection.Connection, None]:
    """openstacksdk Connection 객체를 반환하는 Depends 함수.
    conn._afterglow_token, conn._afterglow_project_id 에 원본 크리덴셜을 저장해
    Manila 등 openstacksdk 외부 클라이언트에서 그대로 사용할 수 있도록 한다.
    요청 완료 후 Connection을 닫아 리소스 누수를 방지한다.
    """
    token_info = await get_token_info(
        authorization=authorization,
        x_auth_token=x_auth_token,
        x_project_id=x_project_id,
    )
    scoped_token = token_info["token"]
    project_id = token_info["project_id"]
    try:
        conn = keystone.get_openstack_connection(scoped_token, project_id)
        conn._afterglow_token = scoped_token
        conn._afterglow_project_id = project_id
        conn._afterglow_user_id = token_info.get("user_id", "")
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")

    try:
        yield conn
    finally:
        await asyncio.to_thread(conn.close)


async def cache_bypass(refresh: bool = Query(False)) -> bool:
    """`?refresh=true` 쿼리스트링으로 캐시 우회를 허용하는 의존성.

    cached_call(key, ttl, fn, refresh=bypass) 와 페어로 사용한다.
    """
    return refresh
