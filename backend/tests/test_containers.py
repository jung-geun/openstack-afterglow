"""container/containers.py 엔드포인트 단위 테스트 (8 HTTP 엔드포인트, Zun 서비스 필요)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.containers import ContainerListResponse, ZunContainerInfo


def _make_container():
    return ZunContainerInfo(
        uuid="c-1", name="mycontainer", status="Running", image="nginx",
        cpu=0.5, memory="128", command=None, created_at=None,
    )


@pytest.mark.asyncio
async def test_list_containers_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/containers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_containers_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=[])
        resp = await client.get("/api/containers")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/containers/c-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_container_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=_make_container())
        resp = await client.get("/api/containers/c-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/containers", json={"name": "test", "image": "nginx"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_container_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=_make_container())
        resp = await client.post("/api/containers", json={"name": "test", "image": "nginx"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/containers/c-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_container_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/containers/c-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_start_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/containers/c-1/start")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_start_container_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.post("/api/containers/c-1/start")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_stop_container_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/containers/c-1/stop")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stop_container_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.post("/api/containers/c-1/stop")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_container_logs_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/containers/c-1/logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_container_logs_success(client):
    with patch("app.api.container.containers.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value="log line 1\n")
        resp = await client.get("/api/containers/c-1/logs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_exec_ticket_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/containers/c-1/exec-ticket")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_exec_ticket_success(client):
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock(return_value=None)
    with patch("app.services.cache._get_redis", new=AsyncMock(return_value=mock_redis)):
        resp = await client.post("/api/containers/c-1/exec-ticket")
    assert resp.status_code == 201
    assert "ticket" in resp.json()
