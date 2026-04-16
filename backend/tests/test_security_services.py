"""storage/security_services.py 엔드포인트 단위 테스트 (5개, manila 필요)."""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_list_security_services_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/security-services")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_security_services_success(client):
    with patch("app.api.storage.security_services.cached_call", new=AsyncMock(return_value=[])):
        resp = await client.get("/api/security-services")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_security_service_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/security-services", json={"type": "ldap", "name": "ss1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_security_service_success(client):
    ss = {"id": "ss-1", "name": "ss1", "type": "ldap", "status": "new",
          "description": "", "dns_ip": None, "server": None, "domain": None,
          "user": None, "created_at": None}
    with patch("app.api.storage.security_services.asyncio") as mock_asyncio, \
         patch("app.api.storage.security_services.invalidate", new=AsyncMock()):
        mock_asyncio.to_thread = AsyncMock(return_value=ss)
        resp = await client.post("/api/security-services", json={"type": "ldap", "name": "ss1"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_security_service_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/security-services/ss-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_security_service_success(client):
    with patch("app.api.storage.security_services.asyncio") as mock_asyncio, \
         patch("app.api.storage.security_services.invalidate", new=AsyncMock()):
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/security-services/ss-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_attach_security_service_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/security-services/ss-1/attach?share_network_id=sn-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_attach_security_service_success(client):
    with patch("app.api.storage.security_services.asyncio") as mock_asyncio, \
         patch("app.api.storage.security_services.invalidate", new=AsyncMock()):
        mock_asyncio.to_thread = AsyncMock(return_value={"id": "sn-1"})
        resp = await client.post("/api/security-services/ss-1/attach?share_network_id=sn-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_detach_security_service_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/security-services/ss-1/detach?share_network_id=sn-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_detach_security_service_success(client):
    with patch("app.api.storage.security_services.asyncio") as mock_asyncio, \
         patch("app.api.storage.security_services.invalidate", new=AsyncMock()):
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/security-services/ss-1/detach?share_network_id=sn-1")
    assert resp.status_code == 204
