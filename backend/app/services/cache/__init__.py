"""Redis 기반 캐시 레이어 — Phase A' 패키지 진입점.

레거시 cache.py 와 동일한 import 경로를 유지하기 위한 backwards-compat wrapper.

키 형식: afterglow:{service}:{project_id}:{resource}
예시: afterglow:nova:abc123:servers

레거시 API (계속 동작 — ~85 call sites):
- cached_call(key, ttl, fn, *, refresh=False)
- invalidate(pattern)
- invalidate_project(project_id, service="*")
- ttl_fast / ttl_normal / ttl_slow / ttl_static
- _get_redis() / _get_client() (object_storage, instance_health, admin_identity 등)

신규 API:
- backend (전역 RedisBackend 싱글톤)
- get_backend() (테스트 주입용 접근자)
- base.Cache (ABC)
- redis_backend.RedisBackend
- keys.* / metrics / invalidation

write-through forbidden 불변식:
mutation 응답 직후 set() 호출 금지. mutation 직후에는 invalidate() / delete() /
invalidate_tag() / bump_version() 만 사용한다. (Nova create_server 의 부분 BUILD
상태가 영구 stale 의 원인이 됨.)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import redis.asyncio as aioredis

from app.services.cache import metrics
from app.services.cache.base import Cache
from app.services.cache.redis_backend import RedisBackend
from app.services.cache.ttl import ttl_fast, ttl_normal, ttl_slow, ttl_static

logger = logging.getLogger(__name__)


_backend: Cache | None = None


def _get_backend() -> Cache:
    """프로세스 전역 캐시 백엔드를 반환 (필요 시 lazy 생성)."""
    global _backend
    if _backend is None:
        _backend = RedisBackend()
    return _backend


def get_backend() -> Cache:
    """외부 노출 백엔드 접근자 — 테스트에서 set_backend() 와 페어로 사용."""
    return _get_backend()


def set_backend(backend: Cache | None) -> None:
    """테스트 전용 — 백엔드 주입 / 리셋."""
    global _backend
    _backend = backend


def _make_serializable(obj: Any) -> Any:
    """Pydantic 모델 등을 JSON 직렬화 가능한 형태로 변환."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_make_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    return obj


def _get_client() -> aioredis.Redis:
    """레거시 호환 — 동기 진입점에서도 raw redis 클라이언트를 반환.

    cache.py 시절 일부 호출부 (compute/instance_health.py) 가 사용.
    """
    backend = _get_backend()
    if isinstance(backend, RedisBackend):
        return backend.raw_client()
    raise RuntimeError("legacy _get_client() requires RedisBackend; current backend is incompatible")


async def _get_redis() -> aioredis.Redis:
    """레거시 호환 — raw redis 클라이언트를 반환 (캐시 레이어 외부 직접 접근용)."""
    return _get_client()


async def cached_call(
    key: str,
    ttl: int,
    fn: Callable[[], Any],
    *,
    refresh: bool = False,
) -> Any:
    """캐시에서 값을 가져오거나, 없으면 fn을 실행하여 저장 후 반환.

    fn 이 동기 함수인 경우 asyncio.to_thread 로 실행한다.
    Redis 연결 실패 시 캐시 없이 fn 을 직접 실행한다 (silent fail).
    refresh=True 이면 기존 캐시를 삭제하고 fn 을 강제 실행한다.
    """
    backend = _get_backend()

    if refresh:
        try:
            await backend.delete(key)
        except Exception:
            pass

    # 1) 캐시 hit 시도
    try:
        cached = await backend.get(key)
        if cached is not None:
            metrics.increment("cache.hit")
            try:
                return json.loads(cached)
            except (TypeError, ValueError) as e:
                # 손상된 캐시: 메트릭만 올리고 fn 으로 폴백
                metrics.increment("cache.error")
                logger.warning("캐시 JSON 디코드 실패 (%s): %s", key, e)
    except Exception as e:
        metrics.increment("cache.error")
        logger.warning("캐시 읽기 실패 (%s): %s", key, e)

    # 2) 캐시 미스 — fn 실행
    metrics.increment("cache.miss")
    if asyncio.iscoroutinefunction(fn):
        result = await fn()
    else:
        result = await asyncio.to_thread(fn)

    # 3) 결과를 캐시에 저장 (read-through 경로 — 허용)
    try:
        payload = json.dumps(_make_serializable(result))
        await backend.set(key, payload, ttl)
    except Exception as e:
        metrics.increment("cache.error")
        logger.warning("캐시 쓰기 실패 (%s): %s", key, e)

    return result


async def invalidate(pattern: str) -> None:
    """패턴에 매칭되는 캐시 키를 모두 삭제.

    KEYS 대신 SCAN 을 사용해 Redis 블로킹을 방지. 와일드카드(`*`) 가 없는 경우
    delete() 단일 호출로 최적화한다. backend 가 RedisBackend 가 아닌 경우
    (Memcached v2) 와일드카드 패턴은 무시되고 정확 키만 삭제된다.
    """
    backend = _get_backend()
    try:
        # 와일드카드가 없으면 단일 키 삭제로 처리
        if "*" not in pattern and "?" not in pattern and "[" not in pattern:
            await backend.delete(pattern)
            return

        # 와일드카드 — SCAN 사용 (RedisBackend 전용 _scan)
        if isinstance(backend, RedisBackend):
            keys_to_delete = await backend._scan(pattern)
            if keys_to_delete:
                await backend.delete(*keys_to_delete)
        else:
            # SCAN 없는 백엔드 — Memcached v2 호환 경로
            logger.debug("backend does not support pattern invalidation (%s)", pattern)
    except Exception as e:
        metrics.increment("cache.error")
        logger.warning("캐시 삭제 실패 (%s): %s", pattern, e)


async def invalidate_project(project_id: str, service: str = "*") -> None:
    """특정 프로젝트의 특정 서비스(또는 전체) 캐시를 삭제."""
    await invalidate(f"afterglow:{service}:{project_id}:*")


__all__ = [
    # 레거시 호환
    "cached_call",
    "invalidate",
    "invalidate_project",
    "ttl_fast",
    "ttl_normal",
    "ttl_slow",
    "ttl_static",
    "_get_redis",
    "_get_client",
    "_make_serializable",
    # 신규
    "Cache",
    "RedisBackend",
    "get_backend",
    "set_backend",
    "metrics",
]
