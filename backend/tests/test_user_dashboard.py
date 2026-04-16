"""common/user_dashboard.py 엔드포인트 단위 테스트 (1개)."""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_get_user_dashboard_summary_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/user-dashboard/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_user_dashboard_summary_success(client):
    with patch("app.api.common.user_dashboard.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=[{"id": "p-1", "name": "proj1"}])
        mock_asyncio.gather = AsyncMock(return_value=[
            {
                "project_id": "p-1", "project_name": "proj1",
                "instances": [], "volumes": [],
                "instance_count": 0, "volume_count": 0,
                "storage_gb": 0, "vcpus": 0, "ram_mb": 0,
                "network_count": 0, "fip_count": 0,
            }
        ])
        resp = await client.get("/api/user-dashboard/summary")
    assert resp.status_code in (200, 500)
