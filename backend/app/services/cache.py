"""Redis 기반 캐시 레이어.

키 형식: union:{service}:{project_id}:{resource}
예시: union:nova:abc123:servers

TTL 정책:
- servers/volumes: 15s
- limits: 30s
- networks/security_groups: 60s
- flavors/images: 300s
"""

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client


async def _get_redis() -> aioredis.Redis:
    """Redis 클라이언트를 반환. 세션 관리 등 캐시 레이어 외부에서 직접 사용 시."""
    return _get_client()


async def cached_call(
    key: str,
    ttl: int,
    fn: Callable[[], Any],
) -> Any:
    """캐시에서 값을 가져오거나, 없으면 fn을 실행하여 저장 후 반환.

    fn이 동기 함수인 경우 asyncio.to_thread로 실행.
    Redis 연결 실패 시 캐시 없이 fn을 직접 실행.
    """
    client = _get_client()
    try:
        cached = await client.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception as e:
        logger.warning("캐시 읽기 실패 (%s): %s", key, e)

    # 캐시 미스 — fn 실행
    if asyncio.iscoroutinefunction(fn):
        result = await fn()
    else:
        result = await asyncio.to_thread(fn)

    try:
        await client.setex(key, ttl, json.dumps(result, default=str))
    except Exception as e:
        logger.warning("캐시 쓰기 실패 (%s): %s", key, e)

    return result


async def invalidate(pattern: str) -> None:
    """패턴에 매칭되는 캐시 키를 모두 삭제."""
    client = _get_client()
    try:
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
    except Exception as e:
        logger.warning("캐시 삭제 실패 (%s): %s", pattern, e)


async def invalidate_project(project_id: str, service: str = "*") -> None:
    """특정 프로젝트의 특정 서비스(또는 전체) 캐시를 삭제."""
    await invalidate(f"union:{service}:{project_id}:*")
