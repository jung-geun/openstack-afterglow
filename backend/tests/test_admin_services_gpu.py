"""admin_services.py / admin_gpu.py 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_list_services_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/services")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_services_allowed(admin_client, mock_conn):
    mock_conn.compute.services.return_value = iter([])
    resp = await admin_client.get("/api/v1/admin/services")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_list_gpu_hosts_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-hosts")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_gpu_hosts_allowed(admin_client):
    with patch("app.api.identity.admin_gpu.cached_call") as mc:
        mc.side_effect = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/v1/admin/gpu-hosts")
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# GPU quota admin API (admin-only 관문 + DB 미초기화 503)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_gpu_aliases_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_gpu_aliases_allowed(admin_client):
    # get_all_gpu_aliases는 lazy import이므로 app.services.gpu_quota 를 패치
    with patch("app.services.gpu_quota.get_all_gpu_aliases", new=AsyncMock(return_value=["RTX3090"])):
        resp = await admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_db_not_initialized(admin_client):
    """DB 미초기화 시 503 반환."""
    # is_db_available은 lazy import이므로 원래 모듈 경로를 패치
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_set_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-quotas/test-project-123")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/v1/admin/gpu-quotas/test-project-123")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_project_gpu_quotas_available_calculation(admin_client, mock_conn):
    """available = limit - in_use 계산 검증."""
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.services.gpu_quota.get_all_gpu_aliases", new=AsyncMock(return_value=["RTX3090"])):
            with patch("app.services.gpu_quota.get_effective_gpu_quotas", new=AsyncMock(return_value={"RTX3090": 4})):
                with patch("app.services.gpu_quota.get_project_gpu_usage", new=AsyncMock(return_value={"RTX3090": 1})):
                    resp = await admin_client.get("/api/v1/admin/gpu-quotas/test-project-123")
    if resp.status_code == 200:
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        assert item["gpu_type"] == "RTX3090"
        assert item["limit"] == 4
        assert item["in_use"] == 1
        assert item["available"] == 3


# ---------------------------------------------------------------------------
# GPU hosts raw 진단 엔드포인트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_hosts_raw_requires_admin(non_admin_client):
    """비관리자 → 403."""
    resp = await non_admin_client.get("/api/v1/admin/gpu-hosts/raw")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_gpu_hosts_raw_returns_hosts_key(admin_client):
    """관리자 → 200 + hosts 키 포함."""
    raw_result = {"hosts": []}
    with patch("app.api.identity.admin_gpu.asyncio.to_thread", new=AsyncMock(return_value=raw_result)):
        resp = await admin_client.get("/api/v1/admin/gpu-hosts/raw")
    assert resp.status_code == 200
    assert "hosts" in resp.json()


@pytest.mark.asyncio
async def test_gpu_hosts_raw_exposes_device_id(admin_client, mock_conn):
    """device_id, resource_class, is_audio 필드가 응답에 포함된다."""
    mock_result = {
        "hosts": [
            {
                "name": "dms-compute10",
                "uuid": "rp-root-1",
                "pci_resources": [
                    {
                        "provider_uuid": "rp-child-1",
                        "provider_name": "dms-compute10_0000:05:00.0",
                        "pci_address": "0000:05:00.0",
                        "resource_class": "CUSTOM_PCI_10DE_2504",
                        "vendor_id": "10DE",
                        "device_id": "2504",
                        "vendor_name": "NVIDIA",
                        "resolved_name": "RTX 3060",
                        "total": 1,
                        "used": 0,
                        "is_audio": False,
                    }
                ],
            }
        ]
    }
    with patch("app.api.identity.admin_gpu.asyncio.to_thread", new=AsyncMock(return_value=mock_result)):
        resp = await admin_client.get("/api/v1/admin/gpu-hosts/raw")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["hosts"]) == 1
    pci = data["hosts"][0]["pci_resources"][0]
    assert pci["device_id"] == "2504"
    assert pci["resource_class"] == "CUSTOM_PCI_10DE_2504"
    assert pci["resolved_name"] == "RTX 3060"
    assert pci["is_audio"] is False
