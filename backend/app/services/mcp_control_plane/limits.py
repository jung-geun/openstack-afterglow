"""Redis-backed per-grant rate and concurrency controls for inbound MCP."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from app.config import get_settings
from app.services.cache import _get_redis
from app.services.mcp_control_plane.authentication import McpPrincipal


class McpRateLimitExceeded(RuntimeError):
    """A verified grant exceeded a bounded request or call budget."""


class McpRateLimitUnavailable(RuntimeError):
    """Redis is required; MCP never downgrades to process-local limiting."""


_SLOT_TTL_SECONDS = 120
_SLOT_ACQUIRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
if count > tonumber(ARGV[1]) then
  redis.call('DECR', KEYS[1])
  return 0
end
return 1
"""


def _base(principal: McpPrincipal) -> str:
    return f"afterglow:mcp:limit:{principal.project_id}:{principal.grant_id}"


async def _check_rate(principal: McpPrincipal, *, effect: Literal["read", "external_mutation"]) -> None:
    settings = get_settings()
    maximum = (
        settings.mcp_mutation_rate_per_minute if effect == "external_mutation" else settings.mcp_read_rate_per_minute
    )
    bucket = int(time.time() // 60)
    try:
        redis = await _get_redis()
        key = f"{_base(principal)}:rate:{effect}:{bucket}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 61)
    except Exception as exc:
        raise McpRateLimitUnavailable("MCP rate limiting is unavailable") from exc
    if count > maximum:
        raise McpRateLimitExceeded("MCP rate limit exceeded")


@asynccontextmanager
async def grant_call_slot(
    principal: McpPrincipal, *, effect: Literal["read", "external_mutation"]
) -> AsyncIterator[None]:
    """Hold one cross-replica concurrency slot through the complete SDK request."""
    await _check_rate(principal, effect=effect)
    settings = get_settings()
    key = f"{_base(principal)}:concurrency"
    try:
        redis = await _get_redis()
        acquired = await redis.eval(_SLOT_ACQUIRE, 1, key, settings.mcp_concurrent_calls, _SLOT_TTL_SECONDS)
    except Exception as exc:
        raise McpRateLimitUnavailable("MCP concurrency limiting is unavailable") from exc
    if int(acquired) != 1:
        raise McpRateLimitExceeded("MCP concurrent call limit exceeded")
    try:
        yield
    finally:
        try:
            await redis.decr(key)
        except Exception:
            # The short TTL is the conservative recovery path; never mask a completed call response.
            pass
