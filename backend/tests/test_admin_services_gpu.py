"""admin_services.py / admin_gpu.py 엔드포인트 단위 테스트 (각 1개)."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_list_services_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/services")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_services_allowed(admin_client, mock_conn):
    mock_conn.compute.services.return_value = iter([])
    resp = await admin_client.get("/api/admin/services")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_list_gpu_hosts_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/gpu-hosts")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_gpu_hosts_allowed(admin_client):
    with patch("app.api.identity.admin_gpu.cached_call") as mc:
        mc.side_effect = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/admin/gpu-hosts")
    assert resp.status_code != 403
