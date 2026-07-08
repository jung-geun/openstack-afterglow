"""Trove DB instance/backup cross-project IDOR 거부 검증."""

from unittest.mock import MagicMock, patch

import pytest


def _foreign(project_id: str = "other-project-999"):
    m = MagicMock()
    m.project_id = project_id
    m.tenant_id = None
    return m


@pytest.mark.asyncio
async def test_get_db_instance_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.get("/api/v1/database-instances/inst-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_db_instance_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.delete("/api/v1/database-instances/inst-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restart_db_instance_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.post("/api/v1/database-instances/inst-foreign/restart")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_enable_root_other_project_returns_404(client, mock_conn):
    """가장 위험한 케이스 — root 비밀번호 발급 endpoint."""
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.post("/api/v1/database-instances/inst-foreign/root")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_enable_root_other_project(admin_client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    with patch(
        "app.api.database.instances.asyncio.to_thread",
        side_effect=lambda fn, *a, **kw: _async_return({"name": "root", "password": "pw"}),
    ):
        # asyncio.to_thread 직접 patch 보다는 trove 함수 patch 가 안전 — 단순화
        pass
    with patch("app.services.trove.enable_root", return_value={"name": "root", "password": "pw"}):
        resp = await admin_client.post("/api/v1/database-instances/inst-foreign/root")
    assert resp.status_code == 200


async def _async_return(v):
    return v


@pytest.mark.asyncio
async def test_create_db_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.post("/api/v1/database-instances/inst-foreign/databases", json={"name": "mydb"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_user_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.post(
        "/api/v1/database-instances/inst-foreign/users",
        json={"name": "u1", "password": "pw"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_db_backup_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_instance = MagicMock(return_value=_foreign())
    resp = await client.post("/api/v1/database-instances/inst-foreign/backups", json={"name": "b1"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_db_backup_other_project_returns_404(client, mock_conn):
    mock_conn.database.get_backup = MagicMock(return_value=_foreign())
    resp = await client.delete("/api/v1/database-instances/backups/bk-foreign")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_from_other_project_backup_returns_404(client, mock_conn):
    mock_conn.database.get_backup = MagicMock(return_value=_foreign())
    resp = await client.post(
        "/api/v1/database-instances/restore",
        json={"backup_id": "bk-foreign", "name": "n", "flavor_id": "f", "volume_size": 1},
    )
    assert resp.status_code == 404
