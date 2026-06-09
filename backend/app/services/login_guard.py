"""계정 브루트포스 방어 — Redis 기반 실패 카운트 + 지수 백오프 잠금."""

import logging
import time

_logger = logging.getLogger(__name__)

_PREFIX = "afterglow:login_guard"


def _fail_key(username: str, domain: str) -> str:
    return f"{_PREFIX}:fail:{username}:{domain}"


def _lock_key(username: str, domain: str) -> str:
    return f"{_PREFIX}:lock:{username}:{domain}"


async def check_locked(username: str, domain: str) -> None:
    """잠금 상태이면 HTTPException(429) 발생."""
    from fastapi import HTTPException

    from app.services.cache import _get_redis

    try:
        r = await _get_redis()
        lock_raw = await r.get(_lock_key(username, domain))
        if lock_raw is not None:
            remaining = int(float(lock_raw) - time.time())
            remaining = max(remaining, 0)
            raise HTTPException(
                status_code=429,
                detail=f"계정이 일시적으로 잠겼습니다. {remaining}초 후 다시 시도하세요.",
                headers={"Retry-After": str(remaining)},
            )
    except HTTPException:
        raise
    except Exception:
        _logger.warning("login_guard.check_locked 실패 — 잠금 확인 건너뜀", exc_info=True)


async def record_failure(username: str, domain: str) -> None:
    """실패 카운트 증가. 임계값 초과 시 지수 백오프로 잠금."""
    from app.config import get_settings
    from app.services.cache import _get_redis

    settings = get_settings()
    max_attempts = settings.login_max_attempts
    lockout_seconds = settings.login_lockout_seconds
    backoff_base = settings.login_backoff_base

    try:
        r = await _get_redis()
        fk = _fail_key(username, domain)
        count = await r.incr(fk)
        # 첫 실패 시 TTL 설정 (잠금 해제 후 카운트도 초기화)
        if count == 1:
            await r.expire(fk, lockout_seconds * (backoff_base**max_attempts))
        if count >= max_attempts:
            # 잠금 지속 시간: 기본 lockout_seconds * backoff_base^(count - max_attempts + 1)
            exponent = min(count - max_attempts, 5)  # 최대 2^5 = 32배 제한
            duration = int(lockout_seconds * (backoff_base**exponent))
            unlock_at = time.time() + duration
            await r.setex(_lock_key(username, domain), duration + 10, str(unlock_at))
            _logger.warning(
                "login_guard: 계정 잠금 (user=%s, domain=%s, count=%d, duration=%ds)",
                username,
                domain,
                count,
                duration,
            )
    except Exception:
        _logger.warning("login_guard.record_failure 실패", exc_info=True)


async def record_success(username: str, domain: str) -> None:
    """로그인 성공 시 실패 카운트 초기화."""
    from app.services.cache import _get_redis

    try:
        r = await _get_redis()
        await r.delete(_fail_key(username, domain))
        await r.delete(_lock_key(username, domain))
    except Exception:
        _logger.warning("login_guard.record_success 실패", exc_info=True)


async def admin_unlock(username: str, domain: str) -> None:
    """관리자 강제 잠금 해제."""
    from app.services.cache import _get_redis

    r = await _get_redis()
    await r.delete(_fail_key(username, domain))
    await r.delete(_lock_key(username, domain))
    _logger.info("login_guard: 관리자 잠금 해제 (user=%s, domain=%s)", username, domain)


async def get_lock_status(username: str, domain: str) -> dict:
    """잠금 상태 조회. 관리자 API용."""
    from app.services.cache import _get_redis

    try:
        r = await _get_redis()
        fk = _fail_key(username, domain)
        lk = _lock_key(username, domain)
        fail_count_raw = await r.get(fk)
        lock_raw = await r.get(lk)
        fail_count = int(fail_count_raw) if fail_count_raw else 0
        locked = lock_raw is not None
        remaining = 0
        if locked:
            remaining = max(0, int(float(lock_raw) - time.time()))
        return {
            "username": username,
            "domain": domain,
            "fail_count": fail_count,
            "locked": locked,
            "remaining_seconds": remaining,
        }
    except Exception:
        return {
            "username": username,
            "domain": domain,
            "fail_count": 0,
            "locked": False,
            "remaining_seconds": 0,
        }
