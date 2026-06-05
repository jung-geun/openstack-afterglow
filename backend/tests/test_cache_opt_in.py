"""캐시 기본값 OFF 전환 + write-through 헬퍼 단위 테스트.

Phase 1 변경사항 검증:
- cached_call(enabled=False) — 캐시 read/write 건너뜀, origin 호출
- cached_call(enabled=True, refresh=True) — 재조회+재저장
- write_through — known-value 직접 set
- patch_list — list 엔트리 surgical 수정/제거/추가
- cache_mode 의존성 — 파라미터 조합 → CacheMode 매핑
"""

from __future__ import annotations

import json

import fakeredis.aioredis as fakeredis
import pytest

from app.api.deps import CacheMode, cache_mode
from app.services.cache import (
    cached_call,
    patch_list,
    set_backend,
    write_through,
)
from app.services.cache.metrics import get as metrics_get
from app.services.cache.metrics import reset as metrics_reset
from app.services.cache.redis_backend import RedisBackend

# ── 픽스처 ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def backend():
    """fakeredis 기반 RedisBackend + 전역 주입."""
    client = fakeredis.FakeRedis(decode_responses=True)
    b = RedisBackend(client=client)
    set_backend(b)
    metrics_reset()
    try:
        yield b
    finally:
        set_backend(None)
        await client.close()


# ── cached_call(enabled=False) ─────────────────────────────────────────────


async def test_cached_call_disabled_skips_read(backend: RedisBackend) -> None:
    """enabled=False 이면 캐시를 읽지 않고 origin 을 호출한다."""
    await backend.set("k", json.dumps({"stale": True}), 60)

    calls = 0

    async def origin():
        nonlocal calls
        calls += 1
        return {"fresh": True}

    result = await cached_call("k", 60, origin, enabled=False)
    assert result == {"fresh": True}
    assert calls == 1


async def test_cached_call_disabled_skips_write(backend: RedisBackend) -> None:
    """enabled=False 이면 origin 결과를 캐시에 저장하지 않는다."""

    async def origin():
        return {"value": 42}

    await cached_call("k", 60, origin, enabled=False)
    # 키가 저장되지 않아야 한다
    assert await backend.get("k") is None


async def test_cached_call_disabled_increments_metric(backend: RedisBackend) -> None:
    """enabled=False 이면 cache.disabled 메트릭을 증가시킨다."""
    metrics_reset()

    async def origin():
        return "x"

    await cached_call("k", 60, origin, enabled=False)
    assert metrics_get("cache.disabled") == 1
    assert metrics_get("cache.hit") == 0
    assert metrics_get("cache.miss") == 0


async def test_cached_call_enabled_default_uses_cache(backend: RedisBackend) -> None:
    """enabled=True(기본) 이면 캐시 hit 시 origin 을 건너뛴다."""
    await backend.set("k", json.dumps({"cached": True}), 60)

    calls = 0

    async def origin():
        nonlocal calls
        calls += 1
        return {"cached": False}

    result = await cached_call("k", 60, origin, enabled=True)
    assert result == {"cached": True}
    assert calls == 0
    assert metrics_get("cache.hit") == 1


async def test_cached_call_sync_fn_disabled(backend: RedisBackend) -> None:
    """enabled=False 일 때 동기 fn 도 asyncio.to_thread 로 실행된다."""

    def sync_origin():
        return {"sync": True}

    result = await cached_call("k", 60, sync_origin, enabled=False)
    assert result == {"sync": True}
    assert await backend.get("k") is None


# ── write_through ──────────────────────────────────────────────────────────


async def test_write_through_sets_value(backend: RedisBackend) -> None:
    """write_through 는 주어진 값을 키에 직접 저장한다."""
    await write_through("detail:k1", 60, {"name": "server-a", "status": "ACTIVE"})
    raw = await backend.get("detail:k1")
    assert raw is not None
    assert json.loads(raw) == {"name": "server-a", "status": "ACTIVE"}


async def test_write_through_overwrites_stale(backend: RedisBackend) -> None:
    """write_through 는 기존 stale 값을 덮어쓴다."""
    await backend.set("detail:k2", json.dumps({"name": "old"}), 60)
    await write_through("detail:k2", 60, {"name": "renamed"})
    raw = await backend.get("detail:k2")
    assert json.loads(raw)["name"] == "renamed"


async def test_write_through_increments_metric(backend: RedisBackend) -> None:
    """write_through 는 cache.write_through 메트릭을 증가시킨다."""
    metrics_reset()
    await write_through("k", 60, {"x": 1})
    assert metrics_get("cache.write_through") == 1


# ── patch_list ─────────────────────────────────────────────────────────────

_ITEMS = [
    {"id": "a1", "name": "Alice"},
    {"id": "b2", "name": "Bob"},
]


async def test_patch_list_add(backend: RedisBackend) -> None:
    """patch_list(add=...) 는 목록 끝에 엔트리를 추가한다."""
    await backend.set("list:k", json.dumps(_ITEMS), 60)
    new_item = {"id": "c3", "name": "Carol"}
    await patch_list("list:k", 60, add=new_item)
    items = json.loads(await backend.get("list:k"))
    assert len(items) == 3
    assert items[-1] == new_item


async def test_patch_list_remove_by_id(backend: RedisBackend) -> None:
    """patch_list(match=id_str, remove=True) 는 id 로 엔트리를 제거한다."""
    await backend.set("list:k", json.dumps(_ITEMS), 60)
    await patch_list("list:k", 60, match="a1", remove=True)
    items = json.loads(await backend.get("list:k"))
    assert len(items) == 1
    assert items[0]["id"] == "b2"


async def test_patch_list_remove_by_callable(backend: RedisBackend) -> None:
    """patch_list(match=callable, remove=True) 는 callable 로 엔트리를 제거한다."""
    await backend.set("list:k", json.dumps(_ITEMS), 60)
    await patch_list("list:k", 60, match=lambda x: x.get("name") == "Bob", remove=True)
    items = json.loads(await backend.get("list:k"))
    assert len(items) == 1
    assert items[0]["name"] == "Alice"


async def test_patch_list_update(backend: RedisBackend) -> None:
    """patch_list(match=id, update=...) 는 엔트리를 교체한다."""
    await backend.set("list:k", json.dumps(_ITEMS), 60)
    updated = {"id": "a1", "name": "Alicia"}
    await patch_list("list:k", 60, match="a1", update=updated)
    items = json.loads(await backend.get("list:k"))
    assert len(items) == 2
    assert items[0] == updated
    assert items[1]["name"] == "Bob"


async def test_patch_list_miss_is_noop(backend: RedisBackend) -> None:
    """캐시 miss 이면 patch_list 는 아무것도 쓰지 않는다 (no-op)."""
    await patch_list("nonexistent", 60, add={"id": "x"})
    assert await backend.get("nonexistent") is None


async def test_patch_list_increments_metric(backend: RedisBackend) -> None:
    """patch_list 는 cache.patch_list 메트릭을 증가시킨다."""
    metrics_reset()
    await backend.set("list:k", json.dumps(_ITEMS), 60)
    await patch_list("list:k", 60, add={"id": "z"})
    assert metrics_get("cache.patch_list") == 1


async def test_patch_list_match_not_found_noop(backend: RedisBackend) -> None:
    """match 에 해당하는 엔트리가 없으면 목록 변경 없이 re-set 한다."""
    await backend.set("list:k", json.dumps(_ITEMS), 60)
    await patch_list("list:k", 60, match="nonexistent_id", remove=True)
    items = json.loads(await backend.get("list:k"))
    assert len(items) == 2  # 변경 없음


# ── cache_mode 의존성 ──────────────────────────────────────────────────────


async def test_cache_mode_default() -> None:
    """파라미터 없음 → enabled=False, refresh=False (origin 직행)."""
    result = await cache_mode(cache=False, refresh=False)
    assert result == CacheMode(enabled=False, refresh=False)


async def test_cache_mode_cache_only() -> None:
    """`?cache=true` → enabled=True, refresh=False (read-through)."""
    result = await cache_mode(cache=True, refresh=False)
    assert result == CacheMode(enabled=True, refresh=False)


async def test_cache_mode_refresh_only() -> None:
    """`?refresh=true` → enabled=True, refresh=True (재조회+재저장)."""
    result = await cache_mode(cache=False, refresh=True)
    assert result == CacheMode(enabled=True, refresh=True)


async def test_cache_mode_both_refresh_wins() -> None:
    """`?cache=true&refresh=true` → refresh 우선 (enabled=True, refresh=True)."""
    result = await cache_mode(cache=True, refresh=True)
    assert result == CacheMode(enabled=True, refresh=True)


# ── cached_call + cache_mode 연동 ─────────────────────────────────────────


async def test_cache_mode_default_bypasses_cache(backend: RedisBackend) -> None:
    """기본 CacheMode(False, False) 로 cached_call 시 캐시를 미접촉."""
    await backend.set("k", json.dumps({"stale": True}), 60)
    cm = CacheMode(enabled=False, refresh=False)
    calls = 0

    async def origin():
        nonlocal calls
        calls += 1
        return {"fresh": True}

    result = await cached_call("k", 60, origin, enabled=cm.enabled, refresh=cm.refresh)
    assert result == {"fresh": True}
    assert calls == 1
    # 캐시에 쓰지 않음 — 기존 stale 값 그대로
    assert json.loads(await backend.get("k")) == {"stale": True}


async def test_cache_mode_opt_in_stores_result(backend: RedisBackend) -> None:
    """`?cache=true` CacheMode 로 캐시 miss → origin 조회 후 저장."""
    cm = CacheMode(enabled=True, refresh=False)

    async def origin():
        return {"value": 99}

    await cached_call("k", 60, origin, enabled=cm.enabled, refresh=cm.refresh)
    stored = await backend.get("k")
    assert json.loads(stored) == {"value": 99}


async def test_cache_mode_refresh_rereads_and_stores(backend: RedisBackend) -> None:
    """`?refresh=true` CacheMode 는 기존 키 삭제 후 재조회+재저장한다."""
    await backend.set("k", json.dumps({"version": 1}), 60)
    cm = CacheMode(enabled=True, refresh=True)

    async def origin():
        return {"version": 2}

    result = await cached_call("k", 60, origin, enabled=cm.enabled, refresh=cm.refresh)
    assert result == {"version": 2}
    stored = json.loads(await backend.get("k"))
    assert stored == {"version": 2}
