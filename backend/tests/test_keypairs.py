"""키페어 API 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest


def make_keypair(name: str = "my-key") -> dict:
    return {
        "name": name,
        "public_key": "ssh-rsa AAAA... user@host",
        "fingerprint": "ab:cd:ef:00",
        "type": "ssh",
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_list_keypairs(client, mock_conn):
    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    with (
        patch("app.api.compute.keypairs.nova.list_keypairs", return_value=[make_keypair()]),
        patch("app.api.compute.keypairs.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/keypairs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["name"] == "my-key"


@pytest.mark.asyncio
async def test_list_keypairs_cache_bypass(client, mock_conn):
    """?refresh=true 쿼리스트링이 cached_call에 refresh=True로 전달되어야 한다."""
    captured = {}

    async def mock_cached_call(key, ttl, fn, *, refresh=False, **kw):
        captured["key"] = key
        captured["refresh"] = refresh
        return fn()

    with (
        patch("app.api.compute.keypairs.nova.list_keypairs", return_value=[make_keypair()]),
        patch("app.api.compute.keypairs.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/keypairs?refresh=true")

    assert resp.status_code == 200
    assert captured.get("refresh") is True
    assert "keypairs" in captured.get("key", "")


@pytest.mark.asyncio
async def test_create_keypair(client, mock_conn):
    with (
        patch("app.api.compute.keypairs.nova.create_keypair", return_value=make_keypair("new-key")),
        patch("app.api.compute.keypairs.invalidate", new=AsyncMock()),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=AsyncMock()),
    ):
        resp = await client.post("/api/keypairs", json={"name": "new-key"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_keypair_invalidates_cache(client, mock_conn):
    """키페어 생성 후 캐시 invalidate + mutation count 증가가 호출되어야 한다."""
    mock_invalidate = AsyncMock()
    mock_mutation_count = AsyncMock()

    with (
        patch("app.api.compute.keypairs.nova.create_keypair", return_value=make_keypair("new-key")),
        patch("app.api.compute.keypairs.invalidate", new=mock_invalidate),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=mock_mutation_count),
    ):
        resp = await client.post("/api/keypairs", json={"name": "new-key"})

    assert resp.status_code == 201
    mock_invalidate.assert_called_once()
    pattern = mock_invalidate.call_args[0][0]
    assert "nova" in pattern
    assert "keypairs" in pattern
    assert pattern.endswith("*")
    mock_mutation_count.assert_called_once_with("nova", mock_conn._afterglow_project_id)


@pytest.mark.asyncio
async def test_delete_keypair(client, mock_conn):
    with (
        patch("app.api.compute.keypairs.nova.delete_keypair", return_value=None),
        patch("app.api.compute.keypairs.invalidate", new=AsyncMock()),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=AsyncMock()),
    ):
        resp = await client.delete("/api/keypairs/my-key")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_keypair_invalidates_cache(client, mock_conn):
    """키페어 삭제 후 캐시 invalidate + mutation count 증가가 호출되어야 한다."""
    mock_invalidate = AsyncMock()
    mock_mutation_count = AsyncMock()

    with (
        patch("app.api.compute.keypairs.nova.delete_keypair", return_value=None),
        patch("app.api.compute.keypairs.invalidate", new=mock_invalidate),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=mock_mutation_count),
    ):
        resp = await client.delete("/api/keypairs/my-key")

    assert resp.status_code == 204
    mock_invalidate.assert_called_once()
    pattern = mock_invalidate.call_args[0][0]
    assert "nova" in pattern
    assert "keypairs" in pattern
    assert pattern.endswith("*")
    mock_mutation_count.assert_called_once_with("nova", mock_conn._afterglow_project_id)
