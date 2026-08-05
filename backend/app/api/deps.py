from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Depends, Header, HTTPException, Query, Request

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


async def _resolve_jwt_token_info(request, bearer_token: str, x_project_id: str | None) -> dict:
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

    # ── 세션 타임아웃 검증 (JWT 경로) ─────────────────────────────────────────
    # refresh_jti를 해시해 X-Auth-Token 경로와 동일한 _check_session_timeout 재사용
    _rjti_hash = hashlib.sha256(refresh_jti.encode()).hexdigest()
    _sess_project_id = sess.get("project_id", x_project_id or "")
    await _check_session_timeout(_rjti_hash, _sess_project_id)

    # ── 블랙리스트 검사 ─────────────────────────────────────────────────────
    if sess.get("blacklisted"):
        raise HTTPException(status_code=401, detail="세션이 차단되었습니다.")

    # ── IP/기기 지문 바인딩 검사 (fail-open: 오류 시 차단 안 함) ───────────
    _username = payload.get("username", "")
    try:
        from app.services.token_binding import check_binding, get_origin

        settings = get_settings()
        cur_ip, cur_fp = get_origin(request)
        action, reason = check_binding(sess, cur_ip, cur_fp, settings.token_ip_binding_mode)
        if action == "block":
            from app.services import activity
            from app.services.session_store import blacklist_session

            asyncio.create_task(blacklist_session(refresh_jti, reason))
            asyncio.create_task(
                activity.record(
                    project_id=sess.get("project_id", ""),
                    user_id=sess.get("user_id", ""),
                    username=_username,
                    resource_type="auth",
                    action="token_origin_mismatch",
                    status="failed",
                    extra={"ip": cur_ip, "origin_ip": sess.get("origin_ip", ""), "reason": reason},
                )
            )
            raise HTTPException(status_code=401, detail="토큰 출처가 일치하지 않습니다.")
        elif action == "log":
            from app.services import activity

            asyncio.create_task(
                activity.record(
                    project_id=sess.get("project_id", ""),
                    user_id=sess.get("user_id", ""),
                    username=_username,
                    resource_type="auth",
                    action="token_origin_mismatch",
                    status="success",
                    extra={
                        "ip": cur_ip,
                        "origin_ip": sess.get("origin_ip", ""),
                        "reason": reason,
                        "blocked": False,
                    },
                )
            )
        else:
            # ok — last_seen 쓰로틀 갱신 (fire-and-forget)
            from app.services.session_store import touch_session_seen

            asyncio.create_task(touch_session_seen(refresh_jti, cur_ip, cur_fp))
    except HTTPException:
        raise
    except Exception:
        # fail-closed: 바인딩 검사 실패(Redis 장애·설정 오류) 시 요청 거부.
        # 운영: Redis 가용성 모니터링 필수 — Redis 장애 시 전체 인증 차단됨.
        _logger.error("토큰 바인딩 검사 실패 — 요청 거부 (fail-closed)", exc_info=True)
        raise HTTPException(
            status_code=401, detail="토큰 바인딩 검사를 완료할 수 없습니다. 잠시 후 다시 시도해 주세요."
        )

    jwt_project_id = payload.get("project_id", "")
    target_project_id = x_project_id or jwt_project_id

    # 권한 정보는 항상 Keystone live 검증(60s 캐시). JWT payload에서 꺼내지 않는다.
    # 프로젝트 전환 여부와 무관하게 동일 경로로 통합 — stale window 제거.
    effective_project_id = target_project_id or sess.get("project_id", jwt_project_id)
    info = await _cached_validate(sess["keystone_token"], effective_project_id)

    # validate_token은 POST /v3/auth/tokens으로 새 Keystone 토큰을 발급한다.
    # 새 토큰이 원본과 다르면 Redis 세션에 역기록해 Keystone TTL 만료 문제를 방지.
    new_ks_token = info.get("token", "")
    if new_ks_token and new_ks_token != sess.get("keystone_token"):
        from app.services.session_store import update_session_token

        asyncio.create_task(update_session_token(refresh_jti, new_ks_token))

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
        "auth_method": sess.get("auth_method", "password"),
        # 출처 필드 — switch_project 원본 운반용
        "origin_ip": sess.get("origin_ip", ""),
        "origin_fp": sess.get("origin_fp", ""),
        # 기기 정보 — switch_project 운반용
        "device_type": sess.get("device_type", ""),
        "os": sess.get("os", ""),
    }


async def get_token_info(
    request: Request,
    authorization: str | None = Header(None),
    x_project_id: str | None = Header(None),
) -> dict:
    """모든 인증 필요 엔드포인트에서 사용하는 Depends 함수.

    Authorization: Bearer <access_jwt> — JWT 경로만 지원.

    request.state.token_info 를 세팅해 activity_audit_middleware 가 자동 로깅 시
    신원(project_id/user_id/username)을 추출할 수 있게 한다.
    """
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization[7:]
        try:
            info = await _resolve_jwt_token_info(request, bearer, x_project_id)
            request.state.token_info = info
            return info
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="세션이 만료되었습니다. 다시 로그인해 주세요.")
    raise HTTPException(status_code=401, detail="Authorization Bearer 토큰이 필요합니다")


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
    request: Request,
    authorization: str | None = Header(None),
    x_project_id: str | None = Header(None),
) -> AsyncGenerator[openstack.connection.Connection, None]:
    """openstacksdk Connection 객체를 반환하는 Depends 함수.
    conn._afterglow_token, conn._afterglow_project_id 에 원본 크리덴셜을 저장해
    Manila 등 openstacksdk 외부 클라이언트에서 그대로 사용할 수 있도록 한다.
    요청 완료 후 Connection을 닫아 리소스 누수를 방지한다.
    """
    token_info = await get_token_info(
        request=request,
        authorization=authorization,
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

    .. deprecated::
        신규 엔드포인트는 cache_mode / CacheMode 를 사용한다.
    """
    return refresh


@dataclass
class CacheMode:
    """캐시 read/write 모드를 담는 값 객체.

    enabled=True, refresh=False  — opt-in read-through (`?cache=true`)
    enabled=True, refresh=True   — 강제 재조회+재저장 (`?refresh=true`)
    enabled=False, refresh=False — origin 직행, 캐시 미접촉 (기본)
    """

    enabled: bool
    refresh: bool


async def cache_mode(
    cache: bool = Query(False, description="캐시 read-through opt-in"),
    refresh: bool = Query(False, description="캐시 강제 갱신(재조회+재저장)"),
) -> CacheMode:
    """`?cache=true` / `?refresh=true` 쿼리를 읽어 CacheMode 를 반환하는 의존성.

    우선순위: refresh > cache > 기본(origin 직행).
    flip-flop 방지: `?refresh=true` 는 재조회+재저장(enabled=True, refresh=True) 으로
    처리해 다음 `?cache=true` 조회가 stale 로 되돌아가지 않도록 한다.
    """
    if refresh:
        return CacheMode(enabled=True, refresh=True)
    if cache:
        return CacheMode(enabled=True, refresh=False)
    return CacheMode(enabled=False, refresh=False)
