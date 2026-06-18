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
        resp = await client.get("/api/v1/keypairs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["name"] == "my-key"


@pytest.mark.asyncio
async def test_list_keypairs_cache_opt_in(client, mock_conn):
    """`?cache=true` 쿼리스트링이 cached_call에 enabled=True로 전달되어야 한다."""
    captured = {}

    async def mock_cached_call(key, ttl, fn, *, enabled=True, refresh=False, **kw):
        captured["key"] = key
        captured["enabled"] = enabled
        captured["refresh"] = refresh
        return fn()

    with (
        patch("app.api.compute.keypairs.nova.list_keypairs", return_value=[make_keypair()]),
        patch("app.api.compute.keypairs.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/v1/keypairs?cache=true")

    assert resp.status_code == 200
    assert captured.get("enabled") is True
    assert captured.get("refresh") is False
    assert "keypairs" in captured.get("key", "")


@pytest.mark.asyncio
async def test_list_keypairs_refresh(client, mock_conn):
    """`?refresh=true` 쿼리스트링이 cached_call에 enabled=True, refresh=True로 전달되어야 한다."""
    captured = {}

    async def mock_cached_call(key, ttl, fn, *, enabled=True, refresh=False, **kw):
        captured["enabled"] = enabled
        captured["refresh"] = refresh
        return fn()

    with (
        patch("app.api.compute.keypairs.nova.list_keypairs", return_value=[make_keypair()]),
        patch("app.api.compute.keypairs.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/v1/keypairs?refresh=true")

    assert resp.status_code == 200
    assert captured.get("enabled") is True
    assert captured.get("refresh") is True


@pytest.mark.asyncio
async def test_list_keypairs_default_no_cache(client, mock_conn):
    """기본 요청(파라미터 없음)은 enabled=False(origin 직행)이어야 한다."""
    captured = {}

    async def mock_cached_call(key, ttl, fn, *, enabled=True, refresh=False, **kw):
        captured["enabled"] = enabled
        return fn()

    with (
        patch("app.api.compute.keypairs.nova.list_keypairs", return_value=[make_keypair()]),
        patch("app.api.compute.keypairs.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/v1/keypairs")

    assert resp.status_code == 200
    assert captured.get("enabled") is False


@pytest.mark.asyncio
async def test_create_keypair(client, mock_conn):
    with (
        patch("app.api.compute.keypairs.nova.create_keypair", return_value=make_keypair("new-key")),
        patch("app.api.compute.keypairs.patch_list", new=AsyncMock()),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=AsyncMock()),
    ):
        resp = await client.post("/api/v1/keypairs", json={"name": "new-key"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_keypair_patches_cache(client, mock_conn):
    """키페어 생성 후 patch_list(add=...) + mutation count 증가가 호출되어야 한다."""
    mock_patch_list = AsyncMock()
    mock_mutation_count = AsyncMock()

    with (
        patch("app.api.compute.keypairs.nova.create_keypair", return_value=make_keypair("new-key")),
        patch("app.api.compute.keypairs.patch_list", new=mock_patch_list),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=mock_mutation_count),
    ):
        resp = await client.post("/api/v1/keypairs", json={"name": "new-key"})

    assert resp.status_code == 201
    mock_patch_list.assert_called_once()
    key_arg = mock_patch_list.call_args[0][0]
    assert "nova" in key_arg
    assert "keypairs" in key_arg
    # add 키워드 인자가 전달되어야 함
    assert "add" in mock_patch_list.call_args[1]
    assert mock_patch_list.call_args[1]["add"]["name"] == "new-key"
    mock_mutation_count.assert_called_once_with("nova", mock_conn._afterglow_project_id)


@pytest.mark.asyncio
async def test_delete_keypair(client, mock_conn):
    with (
        patch("app.api.compute.keypairs.nova.delete_keypair", return_value=None),
        patch("app.api.compute.keypairs.patch_list", new=AsyncMock()),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=AsyncMock()),
    ):
        resp = await client.delete("/api/v1/keypairs/my-key")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_keypair_patches_cache(client, mock_conn):
    """키페어 삭제 후 patch_list(remove=True) + mutation count 증가가 호출되어야 한다."""
    mock_patch_list = AsyncMock()
    mock_mutation_count = AsyncMock()

    with (
        patch("app.api.compute.keypairs.nova.delete_keypair", return_value=None),
        patch("app.api.compute.keypairs.patch_list", new=mock_patch_list),
        patch("app.api.compute.keypairs.invalidation.invalidate_mutation_count", new=mock_mutation_count),
    ):
        resp = await client.delete("/api/v1/keypairs/my-key")

    assert resp.status_code == 204
    mock_patch_list.assert_called_once()
    key_arg = mock_patch_list.call_args[0][0]
    assert "nova" in key_arg
    assert "keypairs" in key_arg
    assert mock_patch_list.call_args[1].get("remove") is True
    mock_mutation_count.assert_called_once_with("nova", mock_conn._afterglow_project_id)
