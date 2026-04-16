"""키페어 API 단위 테스트."""

from unittest.mock import patch

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
async def test_create_keypair(client, mock_conn):
    with patch("app.api.compute.keypairs.nova.create_keypair", return_value=make_keypair("new-key")):
        resp = await client.post("/api/keypairs", json={"name": "new-key"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_keypair(client, mock_conn):
    with patch("app.api.compute.keypairs.nova.delete_keypair", return_value=None):
        resp = await client.delete("/api/keypairs/my-key")
    assert resp.status_code == 204
