"""관리자 쓰기 작업 API 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest

# ────── 비관리자 접근 거부 (403) 테스트 ──────


@pytest.mark.asyncio
async def test_admin_overview_requires_admin(non_admin_client):
    """일반 사용자는 관리자 엔드포인트에 접근 불가 (403)."""
    resp = await non_admin_client.get("/api/admin/overview")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_all_instances_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-instances")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_all_volumes_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-volumes")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_flavors_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/flavors")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_users_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_projects_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/projects")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_hypervisors_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/hypervisors")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_quotas_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/quotas/some-project-id")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_live_migrate_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/instances/inst-1/live-migrate", json={})
    assert resp.status_code == 403


# ────── 관리자 접근 허용 테스트 (403이 아닌 것 확인) ──────


@pytest.mark.asyncio
async def test_admin_access_not_forbidden(admin_client, mock_conn):
    """admin 역할 보유 시 관리자 엔드포인트 접근 가능 (403이 아님)."""
    with patch("app.api.identity.admin.cached_call") as mc:
        mc.side_effect = AsyncMock(
            return_value={
                "hypervisor_count": 0,
                "running_vms": 0,
                "gpu_instances": 0,
                "instance_stats": {},
                "vcpus": {"total": 0, "allowed": 0, "used": 0},
                "ram_gb": {"total": 0, "used": 0},
                "disk_gb": {"total": 0, "used": 0},
                "containers_count": 0,
                "file_storage_count": 0,
            }
        )
        resp = await admin_client.get("/api/admin/overview")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_admin_hypervisors_not_forbidden(admin_client, mock_conn):
    with patch("app.api.identity.admin.cached_call") as mc:
        mc.side_effect = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/admin/hypervisors")
    assert resp.status_code != 403
