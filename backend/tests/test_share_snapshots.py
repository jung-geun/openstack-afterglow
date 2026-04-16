"""storage/share_snapshots.py 엔드포인트 단위 테스트 (3개, manila 필요)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_share_snapshots_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/share-snapshots")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_share_snapshots_success(client):
    with patch("app.api.storage.share_snapshots.cached_call", new=AsyncMock(return_value=[])):
        resp = await client.get("/api/share-snapshots")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_share_snapshot_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/share-snapshots", json={"share_id": "s-1", "name": "snap1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_share_snapshot_success(client):
    snapshot = {
        "id": "snap-1",
        "name": "snap1",
        "status": "available",
        "share_id": "s-1",
        "size": 10,
        "description": None,
        "created_at": None,
    }
    with (
        patch("app.api.storage.share_snapshots.asyncio") as mock_asyncio,
        patch("app.api.storage.share_snapshots.invalidate", new=AsyncMock()),
    ):
        mock_asyncio.to_thread = AsyncMock(return_value=snapshot)
        resp = await client.post("/api/share-snapshots", json={"share_id": "s-1", "name": "snap1"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_share_snapshot_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/share-snapshots/snap-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_share_snapshot_success(client):
    with (
        patch("app.api.storage.share_snapshots.asyncio") as mock_asyncio,
        patch("app.api.storage.share_snapshots.invalidate", new=AsyncMock()),
    ):
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/share-snapshots/snap-1")
    assert resp.status_code == 204
