from types import SimpleNamespace

import pytest

from app.api.identity import admin_resource_policies


def _admin_conn():
    return SimpleNamespace(close=lambda: None)


@pytest.mark.asyncio
async def test_resource_policy_routes_require_admin(non_admin_client):
    response = await non_admin_client.get("/api/v1/admin/resource-policies")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_resource_policy_catalog_uses_backend_admin_connection(admin_client, monkeypatch):
    admin_conn = _admin_conn()

    async def discover(conn, key):
        assert conn is admin_conn
        assert key == "builder.flavor"
        return [{"id": "flavor-1", "name": "builder"}]

    monkeypatch.setattr(admin_resource_policies, "get_admin_project_connection", lambda: admin_conn)
    monkeypatch.setattr(admin_resource_policies.resource_policies, "discover_options", discover)

    response = await admin_client.get("/api/v1/admin/resource-policies/catalog/builder.flavor")

    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "builder.flavor"
    assert body["resource_kind"] == "flavor"
    assert body["execution_scope"] == "service"
    assert body["options"] == [{"id": "flavor-1", "name": "builder"}]


@pytest.mark.asyncio
async def test_resource_policy_update_validates_then_persists(admin_client, monkeypatch):
    saved = {}

    async def set_policy(**kwargs):
        saved.update(kwargs)
        return {"key": kwargs["key"], "resource_id": kwargs["resource_id"]}

    monkeypatch.setattr(admin_resource_policies, "get_admin_project_connection", _admin_conn)
    monkeypatch.setattr(admin_resource_policies.store, "set_policy", set_policy)

    response = await admin_client.put(
        "/api/v1/admin/resource-policies/builder.flavor",
        json={"resource_id": "flavor-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"key": "builder.flavor", "resource_id": "flavor-1"}
    assert saved["key"] == "builder.flavor"
    assert saved["resource_id"] == "flavor-1"
    assert saved["updated_by_user_id"]


@pytest.mark.asyncio
async def test_runtime_settings_persist_typed_values(admin_client, monkeypatch):
    saved = {}

    async def list_runtime_settings():
        return [{"key": "notion.sync_enabled", "value": True, "state": "configured"}]

    async def set_runtime_setting(**kwargs):
        saved.update(kwargs)
        return {"key": kwargs["key"], "value": kwargs["value"]}

    monkeypatch.setattr(admin_resource_policies.store, "list_runtime_settings", list_runtime_settings)
    monkeypatch.setattr(admin_resource_policies.store, "set_runtime_setting", set_runtime_setting)

    response = await admin_client.get("/api/v1/admin/runtime-settings")
    assert response.status_code == 200
    assert response.json()[0]["key"] == "notion.sync_enabled"

    response = await admin_client.put("/api/v1/admin/runtime-settings/notion.sync_enabled", json={"value": False})
    assert response.status_code == 200
    assert response.json() == {"key": "notion.sync_enabled", "value": False}
    assert saved["key"] == "notion.sync_enabled"
    assert saved["value"] is False


@pytest.mark.asyncio
async def test_runtime_settings_require_admin(non_admin_client):
    response = await non_admin_client.get("/api/v1/admin/runtime-settings")
    assert response.status_code == 403
