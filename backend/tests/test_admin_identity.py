"""admin_identity.py 엔드포인트 단위 테스트.

사용자/프로젝트/그룹/역할/할당량 관리 API (22개 엔드포인트).
각 엔드포인트에 대해:
  - non_admin_client → 403
  - admin_client      → 403이 아님 (관문 통과, 실제 응답은 mock에 따라 다양)
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_get_project_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/projects/proj-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_project_returns_shape(admin_client, mock_conn):
    """GET /api/admin/projects/{id} 가 Project shape 를 반환한다."""
    fake_proj = MagicMock()
    fake_proj.id = "proj-abc"
    fake_proj.name = "테스트 프로젝트"
    fake_proj.is_enabled = True
    fake_proj.domain_id = "default"
    fake_proj.created_at = "2024-01-01T00:00:00Z"
    type(fake_proj).__getattr__ = lambda self, k: None  # getattr fallback
    mock_conn.identity.get_project.return_value = fake_proj

    resp = await admin_client.get("/api/admin/projects/proj-abc")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "proj-abc"
    assert data["name"] == "테스트 프로젝트"
    assert data["enabled"] is True
    assert data["domain_id"] == "default"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_project_not_found(admin_client, mock_conn):
    """존재하지 않는 project_id → 404."""
    mock_conn.identity.get_project.side_effect = Exception("Not found")

    resp = await admin_client.get("/api/admin/projects/nonexistent")

    assert resp.status_code == 404


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
async def test_create_project_calls_both_monitoring_sgs(admin_client, mock_conn):
    """프로젝트 생성 시 node_exporter + dcgm_exporter SG 자동 생성 모두 호출 검증."""
    mock_project = MagicMock()
    mock_project.id = "proj-new-1"
    mock_project.name = "test-proj"
    mock_project.description = ""
    mock_project.is_enabled = True
    mock_conn.identity.create_project.return_value = mock_project

    fake_settings = MagicMock()
    fake_settings.monitoring_auto_sg_enabled = True
    fake_settings.monitoring_scrape_cidr = "10.0.0.0/8"
    fake_settings.node_exporter_sg_name = "node_exporter"
    fake_settings.dcgm_exporter_sg_name = "dcgm_exporter"

    ne_called = []
    dc_called = []

    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch(
            "app.services.neutron.ensure_node_exporter_sg",
            side_effect=lambda *a, **kw: ne_called.append(a) or "node_exporter",
        ),
        patch(
            "app.services.neutron.ensure_dcgm_exporter_sg",
            side_effect=lambda *a, **kw: dc_called.append(a) or "dcgm_exporter",
        ),
    ):
        resp = await admin_client.post("/api/admin/projects", json={"name": "test-proj"})

    assert resp.status_code in (200, 201)
    assert len(ne_called) == 1
    assert ne_called[0][1] == "proj-new-1"  # project_id
    assert len(dc_called) == 1
    assert dc_called[0][1] == "proj-new-1"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 역할 할당/회수 audit + 즉시 세션 무효화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_ADMIN_ROLE_ID = "admin-role-id-xyz"
_MEMBER_ROLE_ID = "member-role-id-abc"


@pytest.mark.asyncio
async def test_assign_admin_role_revokes_sessions(admin_client, mock_conn):
    """admin role 할당 시 대상 사용자의 세션이 즉시 무효화되고 audit이 기록된다."""
    mock_conn.identity.assign_project_role_to_user = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=2),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.post(
            "/api/admin/roles/assign",
            json={"user_id": "target-user-1", "project_id": "admin-proj", "role_id": _ADMIN_ROLE_ID},
        )

    assert resp.status_code == 200
    mock_revoke.assert_awaited_once_with("target-user-1")
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "admin_role_grant"
    assert mock_record.call_args.kwargs["resource_id"] == "target-user-1"


@pytest.mark.asyncio
async def test_assign_non_admin_role_no_revoke(admin_client, mock_conn):
    """일반 role 할당 시 세션 무효화는 수행하지 않고 audit만 기록된다."""
    mock_conn.identity.assign_project_role_to_user = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=0),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.post(
            "/api/admin/roles/assign",
            json={"user_id": "target-user-2", "project_id": "some-proj", "role_id": _MEMBER_ROLE_ID},
        )

    assert resp.status_code == 200
    mock_revoke.assert_not_awaited()
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "role_grant"


@pytest.mark.asyncio
async def test_revoke_admin_role_revokes_sessions(admin_client, mock_conn):
    """admin role 회수 시 대상 사용자의 세션이 즉시 무효화되고 audit이 기록된다."""
    mock_conn.identity.unassign_project_role_from_user = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=1),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.delete(
            f"/api/admin/roles/assign?user_id=target-user-3&project_id=admin-proj&role_id={_ADMIN_ROLE_ID}",
        )

    assert resp.status_code == 200
    mock_revoke.assert_awaited_once_with("target-user-3")
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "admin_role_revoke"
    assert mock_record.call_args.kwargs["resource_id"] == "target-user-3"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Security Policy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_security_policy_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/identity/security-policy")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_security_policy_returns_compat_flag_and_count(admin_client):
    """security-policy가 legacy_compat, system_admin_count, admin_project_member_count를 반환한다."""

    def _make_assign(uid: str):
        a = MagicMock()
        a.user = {"id": uid}
        return a

    mock_ks = MagicMock()
    mock_ks.role_assignments.list.side_effect = lambda **kwargs: (
        [_make_assign("sys-1"), _make_assign("sys-2")] if kwargs.get("system") == "all" else [_make_assign("proj-1")]
    )

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=("proj-id", _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
        patch(
            "app.config.get_settings",
            return_value=MagicMock(admin_legacy_project_policy=True),
        ),
    ):
        resp = await admin_client.get("/api/admin/identity/security-policy")

    assert resp.status_code == 200
    data = resp.json()
    assert data["legacy_compat"] is True
    assert data["system_admin_count"] == 2
    assert data["admin_project_member_count"] == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# migrate-from-project
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_migrate_from_project_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/identity/system-roles/migrate-from-project")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_migrate_from_project_grants_only_missing(admin_client):
    """이미 system admin인 멤버는 skip, 아닌 멤버만 grant → migrated/skipped 카운트 정확."""

    def _make_assign(uid: str):
        a = MagicMock()
        a.user = {"id": uid}
        return a

    mock_ks = MagicMock()

    def _list_side(**kwargs):
        if kwargs.get("system") == "all":
            return [_make_assign("already-admin")]
        return [_make_assign("already-admin"), _make_assign("new-admin")]

    mock_ks.role_assignments.list.side_effect = _list_side
    mock_ks.roles.grant = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=("admin-proj-id", _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=1),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.post("/api/admin/identity/system-roles/migrate-from-project")

    assert resp.status_code == 200
    data = resp.json()
    assert data["migrated"] == 1
    assert data["skipped"] == 1
    assert data["errors"] == []
    mock_ks.roles.grant.assert_called_once()
    mock_revoke.assert_awaited_once_with("new-admin")
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "admin_system_role_grant"
    assert mock_record.call_args.kwargs["resource_id"] == "new-admin"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# System Roles (system:all scope)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_system_roles_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/identity/system-roles")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_grant_system_role_revokes_sessions(admin_client):
    """system role grant 시 대상 세션 즉시 무효화 + audit 기록."""
    mock_ks = MagicMock()
    mock_ks.roles.grant = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=1),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.post(
            "/api/admin/identity/system-roles/grant",
            json={"user_id": "target-user-sys"},
        )

    assert resp.status_code == 200
    mock_revoke.assert_awaited_once_with("target-user-sys")
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "admin_system_role_grant"
    assert mock_record.call_args.kwargs["resource_id"] == "target-user-sys"


@pytest.mark.asyncio
async def test_revoke_system_role_revokes_sessions(admin_client):
    """system role revoke 시 대상 세션 즉시 무효화 + audit 기록."""
    mock_ks = MagicMock()
    mock_ks.roles.revoke = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=1),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.post(
            "/api/admin/identity/system-roles/revoke",
            json={"user_id": "target-user-sys"},
        )

    assert resp.status_code == 200
    mock_revoke.assert_awaited_once_with("target-user-sys")
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "admin_system_role_revoke"
    assert mock_record.call_args.kwargs["resource_id"] == "target-user-sys"


@pytest.mark.asyncio
async def test_list_system_roles_returns_enriched_fields(admin_client):
    """list_system_roles 응답에 name/email/enabled 필드가 포함된다."""
    mock_assignment = MagicMock()
    mock_assignment.user = {"id": "sys-user-1"}

    mock_user = MagicMock()
    mock_user.name = "Alice"
    mock_user.email = "alice@example.com"
    mock_user.enabled = True

    mock_ks = MagicMock()
    mock_ks.role_assignments.list.return_value = [mock_assignment]
    mock_ks.users.get.return_value = mock_user

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
    ):
        resp = await admin_client.get("/api/admin/identity/system-roles")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["user_id"] == "sys-user-1"
    assert data[0]["name"] == "Alice"
    assert data[0]["email"] == "alice@example.com"
    assert data[0]["enabled"] is True


@pytest.mark.asyncio
async def test_revoke_last_system_admin_blocked(admin_client):
    """마지막 system admin 회수 시도 → 422."""
    mock_assignment = MagicMock()
    mock_assignment.user = {"id": "last-admin"}

    mock_ks = MagicMock()
    mock_ks.role_assignments.list.return_value = [mock_assignment]

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ),
    ):
        resp = await admin_client.post(
            "/api/admin/identity/system-roles/revoke",
            json={"user_id": "last-admin"},
        )

    assert resp.status_code == 422
    assert "마지막" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_revoke_with_other_admins_succeeds(admin_client):
    """system admin이 2명 이상인 경우 회수 성공 → 200."""

    def _make_assign(uid: str):
        a = MagicMock()
        a.user = {"id": uid}
        return a

    mock_ks = MagicMock()
    mock_ks.role_assignments.list.return_value = [_make_assign("admin-1"), _make_assign("admin-2")]
    mock_ks.roles.revoke = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.keystone._get_admin_ks_client",
            return_value=mock_ks,
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ),
    ):
        resp = await admin_client.post(
            "/api/admin/identity/system-roles/revoke",
            json={"user_id": "admin-1"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_non_admin_role_no_revoke(admin_client, mock_conn):
    """일반 role 회수 시 세션 무효화는 수행하지 않고 audit만 기록된다."""
    mock_conn.identity.unassign_project_role_from_user = MagicMock(return_value=None)

    with (
        patch(
            "app.api.identity.admin_identity.keystone._resolve_admin_ids",
            return_value=(None, _ADMIN_ROLE_ID),
        ),
        patch(
            "app.api.identity.admin_identity.session_store.revoke_user_sessions",
            new=AsyncMock(return_value=0),
        ) as mock_revoke,
        patch(
            "app.api.identity.admin_identity.activity.record",
            new=AsyncMock(),
        ) as mock_record,
    ):
        resp = await admin_client.delete(
            f"/api/admin/roles/assign?user_id=target-user-4&project_id=some-proj&role_id={_MEMBER_ROLE_ID}",
        )

    assert resp.status_code == 200
    mock_revoke.assert_not_awaited()
    mock_record.assert_awaited_once()
    assert mock_record.call_args.kwargs["action"] == "role_revoke"


@pytest.mark.asyncio
async def test_sync_monitoring_sg_returns_both_sg_names(admin_client, mock_conn):
    """sync-monitoring-sg 엔드포인트가 두 SG 이름을 반환한다."""
    fake_settings = MagicMock()
    fake_settings.monitoring_scrape_cidr = "10.0.0.0/8"
    fake_settings.node_exporter_sg_name = "node_exporter"
    fake_settings.dcgm_exporter_sg_name = "dcgm_exporter"

    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch("app.services.neutron.ensure_node_exporter_sg", return_value="node_exporter"),
        patch("app.services.neutron.ensure_dcgm_exporter_sg", return_value="dcgm_exporter"),
    ):
        resp = await admin_client.post("/api/admin/projects/proj-abc/sync-monitoring-sg")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["project_id"] == "proj-abc"
    assert data["sg_names"]["node_exporter"] == "node_exporter"
    assert data["sg_names"]["dcgm_exporter"] == "dcgm_exporter"
