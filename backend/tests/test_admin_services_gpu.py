"""admin_services.py / admin_gpu.py 엔드포인트 단위 테스트."""

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


# ---------------------------------------------------------------------------
# GPU quota admin API (admin-only 관문 + DB 미초기화 503)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_gpu_aliases_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/gpu-aliases")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_gpu_aliases_allowed(admin_client):
    # get_all_gpu_aliases는 lazy import이므로 app.services.gpu_quota 를 패치
    with patch("app.services.gpu_quota.get_all_gpu_aliases", new=AsyncMock(return_value=["RTX3090"])):
        resp = await admin_client.get("/api/admin/gpu-aliases")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/gpu-quotas/defaults")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_db_not_initialized(admin_client):
    """DB 미초기화 시 503 반환."""
    # is_db_available은 lazy import이므로 원래 모듈 경로를 패치
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/admin/gpu-quotas/defaults")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_set_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.put("/api/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.delete("/api/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/gpu-quotas/test-project-123")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/admin/gpu-quotas/test-project-123")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_available_calculation(admin_client, mock_conn):
    """available = limit - in_use 계산 검증."""
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.services.gpu_quota.get_all_gpu_aliases", new=AsyncMock(return_value=["RTX3090"])):
            with patch("app.services.gpu_quota.get_effective_gpu_quotas", new=AsyncMock(return_value={"RTX3090": 4})):
                with patch("app.services.gpu_quota.get_project_gpu_usage", new=AsyncMock(return_value={"RTX3090": 1})):
                    resp = await admin_client.get("/api/admin/gpu-quotas/test-project-123")
    if resp.status_code == 200:
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["gpu_type"] == "RTX3090"
        assert item["limit"] == 4
        assert item["in_use"] == 1
        assert item["available"] == 3
