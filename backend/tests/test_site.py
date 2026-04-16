"""common/site.py 엔드포인트 단위 테스트 (1개 public 엔드포인트)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_site_config_public():
    """GET /api/site-config — 인증 불필요, 항상 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/site-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "site_name" in data
    assert "services" in data


@pytest.mark.asyncio
async def test_get_site_config_contains_service_flags():
    """서비스 플래그 필드 확인."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/site-config")
    services = resp.json()["services"]
    assert "manila" in services
    assert "magnum" in services
    assert "zun" in services
    assert "k3s" in services
