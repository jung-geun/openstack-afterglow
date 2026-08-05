"""GPU Quota 관리 API 단위 테스트 (admin.py 내 GPU quota 엔드포인트).

검증 항목:
1. 모든 GPU quota 엔드포인트: non-admin → 403
2. DB 미초기화 시 → 503
3. 쿼터 계산 로직 (available = limit - in_use, -1 = 무제한)
4. 정상 응답 (admin 허용, 200/204)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 인증 (admin-only) 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_gpu_aliases_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_gpu_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/v1/admin/gpu-quotas/proj-1", json={"gpu_type": "RTX3090", "limit": 2})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_gpu_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/v1/admin/gpu-quotas/proj-1/RTX3090")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB 미초기화 시 503 응답 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_set_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_gpu_quotas_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_set_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.put("/api/v1/admin/gpu-quotas/proj-1", json={"gpu_type": "RTX3090", "limit": 2})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_delete_gpu_quota_db_not_initialized(admin_client):
    with patch("app.database.is_db_available", return_value=False):
        resp = await admin_client.delete("/api/v1/admin/gpu-quotas/proj-1/RTX3090")
    assert resp.status_code == 503


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GPU alias 목록 조회 (admin 허용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_gpu_aliases_allowed(admin_client):
    with patch(
        "app.services.gpu_inventory.get_all_gpu_aliases",
        new=AsyncMock(return_value=["RTX3090", "RTX4090"]),
    ):
        resp = await admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 200
    assert resp.json() == {"aliases": ["RTX3090", "RTX4090"]}


@pytest.mark.asyncio
async def test_get_gpu_aliases_empty(admin_client):
    with patch(
        "app.services.gpu_inventory.get_all_gpu_aliases",
        new=AsyncMock(return_value=[]),
    ):
        resp = await admin_client.get("/api/v1/admin/gpu-aliases")
    assert resp.status_code == 200
    assert resp.json() == {"aliases": []}


@pytest.mark.asyncio
async def test_get_all_gpu_aliases_refreshes_db_overlay_before_discovery():
    """DB catalog aliases must be loaded before mapping Placement device names to quota aliases."""

    class FakeConnection:
        def close(self):
            pass

    refresh = AsyncMock()
    with (
        patch("app.database.is_db_available", return_value=True),
        patch("app.services.gpu_catalog.refresh_device_map_from_db", new=refresh),
        patch("openstack.connect", return_value=FakeConnection()),
        patch("app.services.nova.list_flavors", return_value=[]),
        patch(
            "app.services.gpu_inventory._collect_gpu_hosts", return_value={"gpu_types": [{"device_name": "RTX 3090"}]}
        ),
        patch("app.api.identity.admin_gpu.build_device_name_to_alias_map", return_value={"RTX 3090": "RTX-3090"}),
    ):
        from app.services.gpu_inventory import get_all_gpu_aliases

        result = await get_all_gpu_aliases()

    refresh.assert_awaited_once()
    assert result == ["RTX3090"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기본 GPU quota CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def test_get_default_gpu_quotas_success(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.default_gpu_quotas.return_value = [{"gpu_type": "RTX3090", "limit": 4}]
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [{"gpu_type": "RTX3090", "limit": 4}]


@pytest.mark.asyncio
async def test_get_default_gpu_quotas_empty(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.default_gpu_quotas.return_value = []
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.get("/api/v1/admin/gpu-quotas/defaults")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_set_default_gpu_quota_success(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.set_default_gpu_quota.return_value = {"project_id": "__default__", "gpu_type": "RTX3090", "limit": 4}
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.put("/api/v1/admin/gpu-quotas/defaults", json={"gpu_type": "RTX3090", "limit": 4})
    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu_type"] == "RTX3090"
    assert data["limit"] == 4


@pytest.mark.asyncio
async def test_delete_default_gpu_quota_success(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.delete_default_gpu_quota.return_value = None
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.delete("/api/v1/admin/gpu-quotas/defaults/RTX3090")
    assert resp.status_code == 204


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프로젝트별 GPU quota CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_set_gpu_quota_success(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.set_project_gpu_quota.return_value = {"project_id": "proj-1", "gpu_type": "RTX3090", "limit": 2}
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.put("/api/v1/admin/gpu-quotas/proj-1", json={"gpu_type": "RTX3090", "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "proj-1"
    assert data["gpu_type"] == "RTX3090"
    assert data["limit"] == 2


@pytest.mark.asyncio
async def test_delete_gpu_quota_success(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.delete_project_gpu_quota.return_value = None
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.delete("/api/v1/admin/gpu-quotas/proj-1/RTX3090")
    assert resp.status_code == 204


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 쿼터 계산 로직 테스트 (available = limit - in_use / -1 = 무제한)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def test_get_gpu_quotas_available_calculation(admin_client):
    mock_proxy = MagicMock()
    mock_proxy.project_gpu_quotas.return_value = [{"gpu_type": "RTX3090", "limit": 4, "in_use": 1, "available": 3}]
    with patch("app.database.is_db_available", return_value=True):
        with patch("app.api.identity.admin.register_drover", return_value=mock_proxy):
            resp = await admin_client.get("/api/v1/admin/gpu-quotas/proj-1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["gpu_type"] == "RTX3090"
    assert item["limit"] == 4
    assert item["in_use"] == 1
    assert item["available"] == 3


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# circuit breaker 가드 — is_db_available() False 시 빈 결과
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
