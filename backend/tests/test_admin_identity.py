"""admin_identity.py 엔드포인트 단위 테스트.

사용자/프로젝트/그룹/역할/할당량 관리 API (22개 엔드포인트).
각 엔드포인트에 대해:
  - non_admin_client → 403
  - admin_client      → 403이 아님 (관문 통과, 실제 응답은 mock에 따라 다양)
"""

from unittest.mock import MagicMock, patch

import pytest

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 사용자 관리 (3개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_users_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_allowed(admin_client, mock_conn):
    mock_conn.identity.users.return_value = iter([])
    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_create_user_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/users", json={"name": "u", "password": "pw"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_requires_admin(non_admin_client):
    resp = await non_admin_client.patch("/api/admin/users/user-1", json={"name": "u"})
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 프로젝트 관리 (6개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_project_names_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/projects/names")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_projects_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/projects")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_projects_allowed(admin_client, mock_conn):
    mock_conn.identity.projects.return_value = iter([])
    resp = await admin_client.get("/api/admin/projects")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_create_project_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/projects", json={"name": "p"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_project_requires_admin(non_admin_client):
    resp = await non_admin_client.patch("/api/admin/projects/proj-1", json={"name": "p"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_project_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/projects/proj-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_project_members_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/projects/proj-1/members")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 할당량 (2개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/quotas/proj-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/admin/quotas/proj-1", json={"cores": 20})
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 그룹 관리 (6개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_groups_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/groups")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_groups_allowed(admin_client, mock_conn):
    mock_conn.identity.groups.return_value = iter([])
    resp = await admin_client.get("/api/admin/groups")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_create_group_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/groups", json={"name": "g"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_group_requires_admin(non_admin_client):
    resp = await non_admin_client.patch("/api/admin/groups/grp-1", json={"name": "g"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_group_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/groups/grp-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_group_users_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/groups/grp-1/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_user_to_group_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/admin/groups/grp-1/users/user-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_remove_user_from_group_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/groups/grp-1/users/user-1")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 역할 관리 (5개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_roles_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/roles")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_roles_allowed(admin_client, mock_conn):
    mock_conn.identity.roles.return_value = iter([])
    resp = await admin_client.get("/api/admin/roles")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_assign_role_requires_admin(non_admin_client):
    resp = await non_admin_client.post(
        "/api/admin/roles/assign", json={"user_id": "u", "project_id": "p", "role_id": "r"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revoke_role_requires_admin(non_admin_client):
    resp = await non_admin_client.delete(
        "/api/admin/roles/assign", params={"user_id": "u", "project_id": "p", "role_id": "r"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_assign_group_role_requires_admin(non_admin_client):
    resp = await non_admin_client.post(
        "/api/admin/roles/assign-group", json={"group_id": "g", "project_id": "p", "role_id": "r"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revoke_group_role_requires_admin(non_admin_client):
    resp = await non_admin_client.delete(
        "/api/admin/roles/assign-group", params={"group_id": "g", "project_id": "p", "role_id": "r"}
    )
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Monitoring SG auto-attach (프로젝트 생성 시)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_create_project_calls_ensure_monitoring_sg(admin_client, mock_conn):
    """프로젝트 생성 시 monitoring SG 자동 생성 호출 검증."""
    mock_project = MagicMock()
    mock_project.id = "proj-new-1"
    mock_project.name = "test-proj"
    mock_project.description = ""
    mock_project.is_enabled = True
    mock_conn.identity.create_project.return_value = mock_project

    fake_settings = MagicMock()
    fake_settings.monitoring_auto_sg_enabled = True
    fake_settings.monitoring_scrape_cidr = "10.0.0.0/8"
    fake_settings.monitoring_sg_name = "monitoring"

    mon_called = []

    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch(
            "app.services.neutron.ensure_monitoring_ingress_sg",
            side_effect=lambda *a, **kw: mon_called.append(a) or "monitoring",
        ),
    ):
        resp = await admin_client.post("/api/admin/projects", json={"name": "test-proj"})

    assert resp.status_code in (200, 201)
    assert len(mon_called) == 1
    assert mon_called[0][1] == "proj-new-1"  # project_id
