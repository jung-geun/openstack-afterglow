"""Barbican Key Manager 관리자 — 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_admin_conn():
    """get_admin_project_connection 반환값용 mock conn."""
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


@pytest.mark.asyncio
async def test_list_project_quotas_non_admin_returns_403(non_admin_client):
    r = await non_admin_client.get("/api/admin/key-manager/project-quotas")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_project_quotas_admin_success(admin_client):
    mock_conn = _mock_admin_conn()
    quota_result = [{"project_id": "proj-1", "project_quotas": {"secrets": 100}}]
    with patch("app.api.identity.admin_secrets.asyncio") as mock_asyncio:
        # to_thread 호출 순서: (1) get_admin_project_connection, (2) list_project_quotas, (3) conn.close
        mock_asyncio.to_thread = AsyncMock(side_effect=[mock_conn, quota_result, None])
        r = await admin_client.get("/api/admin/key-manager/project-quotas")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_set_project_quota_non_admin_returns_403(non_admin_client):
    r = await non_admin_client.put("/api/admin/key-manager/project-quotas/proj-1", json={"secrets": 50})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_set_project_quota_admin_success(admin_client):
    mock_conn = _mock_admin_conn()
    with patch("app.api.identity.admin_secrets.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(side_effect=[mock_conn, {"project_quotas": {"secrets": 50}}, None])
        r = await admin_client.put("/api/admin/key-manager/project-quotas/proj-1", json={"secrets": 50})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_set_project_quota_empty_body_returns_422(admin_client):
    r = await admin_client.put("/api/admin/key-manager/project-quotas/proj-1", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_project_quota_non_admin_returns_403(non_admin_client):
    r = await non_admin_client.delete("/api/admin/key-manager/project-quotas/proj-1")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_project_quota_admin_success(admin_client):
    mock_conn = _mock_admin_conn()
    with patch("app.api.identity.admin_secrets.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(side_effect=[mock_conn, None, None])
        r = await admin_client.delete("/api/admin/key-manager/project-quotas/proj-1")
    assert r.status_code == 204
