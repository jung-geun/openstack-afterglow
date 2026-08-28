"""Behavioral proof for the disposable local functional environment."""

import os
from uuid import uuid4

import pytest

from app.services import cache as cache_mod

pytestmark = pytest.mark.db


@pytest.mark.asyncio
async def test_functional_layer_uses_real_redis():
    assert os.environ.get("AFTERGLOW_TEST_REAL_REDIS") == "1"

    client = await cache_mod._get_redis()
    key = f"afterglow:functional:{uuid4()}"
    try:
        assert await client.ping() is True
        await client.set(key, "ok", ex=30)
        assert await client.get(key) == "ok"
    finally:
        await client.delete(key)
        await client.close()
