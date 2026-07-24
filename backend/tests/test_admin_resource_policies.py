import pytest

from app.api.identity import admin_resource_policies


@pytest.mark.asyncio
async def test_resource_policy_routes_require_admin(non_admin_client):
    response = await non_admin_client.get("/api/v1/admin/resource-policies")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_resource_policy_catalog_returns_discovered_options(admin_client, monkeypatch):
    async def discover(_conn, key):
        assert key == "builder.image"
        return [{"id": "image-1", "name": "Ubuntu"}]

    monkeypatch.setattr(admin_resource_policies.resource_policies, "discover_options", discover)

    response = await admin_client.get("/api/v1/admin/resource-policies/catalog/builder.image")

    assert response.status_code == 200
    assert response.json() == {
        "key": "builder.image",
        "resource_kind": "image",
        "options": [{"id": "image-1", "name": "Ubuntu"}],
    }


@pytest.mark.asyncio
async def test_resource_policy_update_validates_then_persists(admin_client, monkeypatch):
    saved = {}

    async def set_policy(**kwargs):
        saved.update(kwargs)
        return {"key": kwargs["key"], "resource_id": kwargs["resource_id"]}

    monkeypatch.setattr(admin_resource_policies.store, "set_policy", set_policy)

    response = await admin_client.put(
        "/api/v1/admin/resource-policies/builder.image",
        json={"resource_id": "image-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"key": "builder.image", "resource_id": "image-1"}
    assert saved["key"] == "builder.image"
    assert saved["resource_id"] == "image-1"
    assert saved["updated_by_user_id"]
