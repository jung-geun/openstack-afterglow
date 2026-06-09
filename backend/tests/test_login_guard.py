"""C1: 계정 잠금 서브시스템 테스트"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeRedis:
    """인메모리 Redis 스텁."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int):
        self._ttls[key] = seconds

    async def setex(self, key: str, seconds: int, value: str):
        self._store[key] = value
        self._ttls[key] = seconds

    async def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)
            self._ttls.pop(k, None)


def _make_settings(max_attempts=5, lockout_seconds=60, backoff_base=2):
    s = MagicMock()
    s.login_max_attempts = max_attempts
    s.login_lockout_seconds = lockout_seconds
    s.login_backoff_base = backoff_base
    return s


@pytest.mark.asyncio
async def test_not_locked_allows_login():
    """잠금 없을 때 check_locked가 아무 예외도 발생시키지 않는다."""
    redis = _FakeRedis()
    with patch("app.services.cache._get_redis", AsyncMock(return_value=redis)):
        from app.services import login_guard

        await login_guard.check_locked("alice", "Default")  # 예외 없어야 함


@pytest.mark.asyncio
async def test_locked_raises_429():
    """잠금 키가 있으면 HTTPException 429를 발생시킨다."""
    from fastapi import HTTPException

    redis = _FakeRedis()
    # 미래 시각으로 잠금 키 주입
    unlock_at = time.time() + 120
    redis._store["afterglow:login_guard:lock:bob:Default"] = str(unlock_at)

    with patch("app.services.cache._get_redis", AsyncMock(return_value=redis)):
        from app.services import login_guard

        with pytest.raises(HTTPException) as exc_info:
            await login_guard.check_locked("bob", "Default")
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_failure_increments_count():
    """record_failure 호출 시 카운트가 증가한다."""
    redis = _FakeRedis()
    settings = _make_settings(max_attempts=5)

    with (
        patch("app.services.cache._get_redis", AsyncMock(return_value=redis)),
        patch("app.config.get_settings", return_value=settings),
    ):
        from app.services import login_guard

        await login_guard.record_failure("carol", "Default")
        await login_guard.record_failure("carol", "Default")

    count = int(redis._store.get("afterglow:login_guard:fail:carol:Default", 0))
    assert count == 2


@pytest.mark.asyncio
async def test_success_resets_count():
    """record_success 호출 시 실패 카운트와 잠금 키가 삭제된다."""
    redis = _FakeRedis()
    redis._store["afterglow:login_guard:fail:dave:Default"] = "3"
    redis._store["afterglow:login_guard:lock:dave:Default"] = str(time.time() + 60)

    with patch("app.services.cache._get_redis", AsyncMock(return_value=redis)):
        from app.services import login_guard

        await login_guard.record_success("dave", "Default")

    assert "afterglow:login_guard:fail:dave:Default" not in redis._store
    assert "afterglow:login_guard:lock:dave:Default" not in redis._store


@pytest.mark.asyncio
async def test_admin_unlock_clears_lock():
    """admin_unlock 호출 시 잠금·실패 키가 모두 삭제된다."""
    redis = _FakeRedis()
    redis._store["afterglow:login_guard:fail:eve:Default"] = "7"
    redis._store["afterglow:login_guard:lock:eve:Default"] = str(time.time() + 200)

    with patch("app.services.cache._get_redis", AsyncMock(return_value=redis)):
        from app.services import login_guard

        await login_guard.admin_unlock("eve", "Default")

    assert "afterglow:login_guard:fail:eve:Default" not in redis._store
    assert "afterglow:login_guard:lock:eve:Default" not in redis._store


@pytest.mark.asyncio
async def test_exponential_backoff():
    """임계값 초과 시 잠금이 설정되고, 추가 실패 시 더 길게 잠긴다."""
    redis = _FakeRedis()
    # max_attempts=3, lockout=10s, base=2
    settings = _make_settings(max_attempts=3, lockout_seconds=10, backoff_base=2)

    with (
        patch("app.services.cache._get_redis", AsyncMock(return_value=redis)),
        patch("app.config.get_settings", return_value=settings),
    ):
        from app.services import login_guard

        # 3회 실패 → 잠금 (exponent=0, duration=10s)
        for _ in range(3):
            await login_guard.record_failure("frank", "Default")

    lock_key = "afterglow:login_guard:lock:frank:Default"
    assert lock_key in redis._store
    first_ttl = redis._ttls[lock_key]
    assert first_ttl >= 10  # duration(10) + 10

    # 4번째 실패 → exponent=1, duration=20s
    with (
        patch("app.services.cache._get_redis", AsyncMock(return_value=redis)),
        patch("app.config.get_settings", return_value=settings),
    ):
        from app.services import login_guard

        await login_guard.record_failure("frank", "Default")

    second_ttl = redis._ttls[lock_key]
    assert second_ttl > first_ttl


@pytest.mark.asyncio
async def test_redis_failure_is_fail_open():
    """Redis 장애 시 check_locked는 예외를 삼키고 로그인을 허용한다."""
    broken_redis = MagicMock()
    broken_redis.get = AsyncMock(side_effect=ConnectionError("redis down"))

    with patch("app.services.cache._get_redis", AsyncMock(return_value=broken_redis)):
        from app.services import login_guard

        # 예외가 전파되지 않아야 한다
        await login_guard.check_locked("grace", "Default")


@pytest.mark.asyncio
async def test_get_lock_status_not_locked():
    """잠금 없는 계정의 상태 조회는 locked=False를 반환한다."""
    redis = _FakeRedis()

    with patch("app.services.cache._get_redis", AsyncMock(return_value=redis)):
        from app.services import login_guard

        status = await login_guard.get_lock_status("henry", "Default")

    assert status["locked"] is False
    assert status["fail_count"] == 0
    assert status["remaining_seconds"] == 0


@pytest.mark.asyncio
async def test_get_lock_status_locked():
    """잠금된 계정의 상태 조회는 locked=True와 양수 remaining_seconds를 반환한다."""
    redis = _FakeRedis()
    unlock_at = time.time() + 90
    redis._store["afterglow:login_guard:fail:ivan:Default"] = "5"
    redis._store["afterglow:login_guard:lock:ivan:Default"] = str(unlock_at)

    with patch("app.services.cache._get_redis", AsyncMock(return_value=redis)):
        from app.services import login_guard

        status = await login_guard.get_lock_status("ivan", "Default")

    assert status["locked"] is True
    assert status["fail_count"] == 5
    assert status["remaining_seconds"] > 0
