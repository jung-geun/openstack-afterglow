"""Phase A' Cache ABC + RedisBackend 단위 테스트.

fakeredis 로 실 Redis 없이 백엔드 ABC 계약을 검증한다. 모든 fixture/test 는
pytest-asyncio auto 모드 (backend/pyproject.toml 의 `asyncio_mode = "auto"`) 에 의존.
"""

from __future__ import annotations

import json

import fakeredis.aioredis as fakeredis
import pytest

from app.services.cache import (
    cached_call,
    invalidate,
    invalidate_project,
    set_backend,
)
from app.services.cache.keys import (
    admin_key,
    mutcount_key,
    project_key,
    tag_key,
    user_key,
    version_key,
)
from app.services.cache.metrics import get as metrics_get
from app.services.cache.metrics import reset as metrics_reset
from app.services.cache.redis_backend import RedisBackend


@pytest.fixture
async def backend():
    """fakeredis 기반 RedisBackend. 전역 _backend 도 함께 주입한다."""
    client = fakeredis.FakeRedis(decode_responses=True)
    b = RedisBackend(client=client)
    set_backend(b)
    metrics_reset()
    try:
        yield b
    finally:
        set_backend(None)
        await client.close()


# ── ABC 기본 동작 ────────────────────────────────────────────────────────────
async def test_get_miss(backend: RedisBackend) -> None:
    assert await backend.get("afterglow:missing") is None


async def test_set_then_get(backend: RedisBackend) -> None:
    await backend.set("afterglow:k", "hello", ttl=10)
    assert await backend.get("afterglow:k") == "hello"


async def test_delete(backend: RedisBackend) -> None:
    await backend.set("k1", "v1", ttl=10)
    await backend.set("k2", "v2", ttl=10)
    count = await backend.delete("k1", "k2", "nonexistent")
    assert count == 2
    assert await backend.get("k1") is None
    assert await backend.get("k2") is None


async def test_delete_empty(backend: RedisBackend) -> None:
    assert await backend.delete() == 0


async def test_incr(backend: RedisBackend) -> None:
    assert await backend.incr("counter") == 1
    assert await backend.incr("counter") == 2
    assert await backend.incr("counter", ttl=60) == 3


async def test_add_to_tag_and_invalidate_tag(backend: RedisBackend) -> None:
    # 두 개의 캐시 키를 같은 태그로 묶는다
    await backend.set("afterglow:nova:p1:servers", "S", ttl=10)
    await backend.set("afterglow:nova:p1:limits", "L", ttl=10)
    await backend.add_to_tag("nova:p1", "afterglow:nova:p1:servers")
    await backend.add_to_tag("nova:p1", "afterglow:nova:p1:limits")

    removed = await backend.invalidate_tag("nova:p1")
    # 캐시 키 2개가 삭제되어야 한다 (tag SET 자체는 카운트에서 제외)
    assert removed == 2
    assert await backend.get("afterglow:nova:p1:servers") is None
    assert await backend.get("afterglow:nova:p1:limits") is None


async def test_invalidate_tag_empty_set(backend: RedisBackend) -> None:
    # 빈 태그에 대해서도 silent 하게 0 을 반환
    assert await backend.invalidate_tag("nova:empty") == 0


async def test_ping(backend: RedisBackend) -> None:
    assert await backend.ping() is True


async def test_close_idempotent(backend: RedisBackend) -> None:
    await backend.close()
    # close 후 호출해도 silent 하게 동작
    await backend.close()


# ── 키 빌더 ─────────────────────────────────────────────────────────────────
def test_key_builders() -> None:
    assert project_key("nova", "p1", "servers") == "afterglow:nova:p1:servers"
    assert project_key("nova", "p1", "servers", sub="x") == "afterglow:nova:p1:servers:x"
    assert user_key("u1", "gpu_quota") == "afterglow:user:u1:gpu_quota"
    assert admin_key("projects") == "afterglow:admin:projects"
    assert tag_key("nova", "p1") == "tag:nova:p1"
    assert mutcount_key("nova", "p1") == "afterglow:mutcount:nova:p1"
    assert version_key("nova", "p1") == "afterglow:ver:nova:p1"


# ── cached_call (레거시 API) ────────────────────────────────────────────────
async def test_cached_call_miss_then_hit(backend: RedisBackend) -> None:
    calls = {"n": 0}

    def fn() -> dict:
        calls["n"] += 1
        return {"value": calls["n"]}

    # 첫 호출: miss → fn 실행 → 저장
    r1 = await cached_call("afterglow:test:k1", 60, fn)
    assert r1 == {"value": 1}
    assert calls["n"] == 1
    assert metrics_get("cache.miss") == 1

    # 두번째 호출: hit → fn 미실행
    r2 = await cached_call("afterglow:test:k1", 60, fn)
    assert r2 == {"value": 1}
    assert calls["n"] == 1
    assert metrics_get("cache.hit") == 1


async def test_cached_call_refresh(backend: RedisBackend) -> None:
    calls = {"n": 0}

    async def fn() -> dict:
        calls["n"] += 1
        return {"value": calls["n"]}

    await cached_call("afterglow:test:k2", 60, fn)
    # refresh=True → 캐시 무시하고 재실행
    r = await cached_call("afterglow:test:k2", 60, fn, refresh=True)
    assert r == {"value": 2}
    assert calls["n"] == 2


async def test_cached_call_serializes_pydantic_like() -> None:
    """model_dump() 가 호출되어 JSON 직렬화 가능 형태로 변환되어야 한다."""
    client = fakeredis.FakeRedis(decode_responses=True)
    b = RedisBackend(client=client)
    set_backend(b)
    try:

        class Pseudo:
            def model_dump(self) -> dict:
                return {"id": 7, "name": "ok"}

        result = await cached_call("afterglow:test:pyd", 30, lambda: Pseudo())
        assert isinstance(result, Pseudo)

        # 저장된 캐시는 dump 된 형태여야 한다
        raw = await b.get("afterglow:test:pyd")
        assert json.loads(raw) == {"id": 7, "name": "ok"}
    finally:
        set_backend(None)
        await client.close()


# ── invalidate / invalidate_project (레거시 헬퍼) ────────────────────────────
async def test_invalidate_exact_key(backend: RedisBackend) -> None:
    await backend.set("afterglow:nova:p1:servers", "x", ttl=60)
    await invalidate("afterglow:nova:p1:servers")
    assert await backend.get("afterglow:nova:p1:servers") is None


async def test_invalidate_pattern_uses_scan(backend: RedisBackend) -> None:
    await backend.set("afterglow:nova:p1:servers", "1", ttl=60)
    await backend.set("afterglow:nova:p1:limits", "2", ttl=60)
    await backend.set("afterglow:nova:p2:servers", "3", ttl=60)

    await invalidate("afterglow:nova:p1:*")
    assert await backend.get("afterglow:nova:p1:servers") is None
    assert await backend.get("afterglow:nova:p1:limits") is None
    # 다른 프로젝트는 영향 없어야 한다
    assert await backend.get("afterglow:nova:p2:servers") == "3"


async def test_invalidate_project_all_services(backend: RedisBackend) -> None:
    await backend.set("afterglow:nova:p1:servers", "x", ttl=60)
    await backend.set("afterglow:neutron:p1:networks", "y", ttl=60)
    await invalidate_project("p1")
    assert await backend.get("afterglow:nova:p1:servers") is None
    assert await backend.get("afterglow:neutron:p1:networks") is None


async def test_invalidate_project_specific_service(backend: RedisBackend) -> None:
    await backend.set("afterglow:nova:p1:servers", "x", ttl=60)
    await backend.set("afterglow:neutron:p1:networks", "y", ttl=60)
    await invalidate_project("p1", service="nova")
    assert await backend.get("afterglow:nova:p1:servers") is None
    # neutron 은 살아 있어야 한다
    assert await backend.get("afterglow:neutron:p1:networks") == "y"
