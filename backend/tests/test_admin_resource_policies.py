from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse

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
async def test_resource_policy_list_merges_waygate_service_and_filters_local_duplicates(admin_client, monkeypatch):
    async def inspect(_conn):
        return [
            {"key": "builder.flavor", "state": "configured"},
            {"key": "waygate.image", "state": "stale-local"},
        ]

    async def remote(service_type, _request, upstream_path):
        assert service_type == "waygate"
        assert upstream_path == "/v1/admin/resource-policies"
        return [{"key": "waygate.image", "state": "configured"}]

    monkeypatch.setattr(admin_resource_policies, "get_admin_project_connection", _admin_conn)
    monkeypatch.setattr(admin_resource_policies.store, "inspect_policies", inspect)
    monkeypatch.setattr(admin_resource_policies, "get_json", remote)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=True, service_k3s_enabled=False),
    )

    response = await admin_client.get("/api/v1/admin/resource-policies")

    assert response.status_code == 200
    assert response.json() == [
        {"key": "builder.flavor", "state": "configured"},
        {"key": "waygate.image", "state": "configured"},
    ]


@pytest.mark.asyncio
async def test_resource_policy_list_merges_drover_service_and_filters_local_duplicates(admin_client, monkeypatch):
    async def inspect(_conn):
        return [
            {"key": "builder.flavor", "state": "configured"},
            {"key": "k3s.server_image", "state": "stale-local"},
        ]

    async def remote(service_type, _request, upstream_path):
        assert service_type == "drover"
        assert upstream_path == "/v1/admin/resource-policies"
        return [{"key": "k3s.server_image", "state": "configured"}]

    monkeypatch.setattr(admin_resource_policies, "get_admin_project_connection", _admin_conn)
    monkeypatch.setattr(admin_resource_policies.store, "inspect_policies", inspect)
    monkeypatch.setattr(admin_resource_policies, "get_json", remote)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=False, service_k3s_enabled=True),
    )

    response = await admin_client.get("/api/v1/admin/resource-policies")

    assert response.status_code == 200
    assert response.json() == [
        {"key": "builder.flavor", "state": "configured"},
        {"key": "k3s.server_image", "state": "configured"},
    ]


@pytest.mark.asyncio
async def test_drover_policy_catalog_proxies_without_backend_admin_connection(admin_client, monkeypatch):
    async def remote(service_type, _request, upstream_path):
        assert service_type == "drover"
        assert upstream_path == "/v1/admin/resource-policies/catalog/k3s.server_image"
        return {"key": "k3s.server_image", "options": []}

    monkeypatch.setattr(
        admin_resource_policies,
        "get_admin_project_connection",
        lambda: pytest.fail("Drover policy must not open the Afterglow admin connection"),
    )
    monkeypatch.setattr(admin_resource_policies, "get_json", remote)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=False, service_k3s_enabled=True),
    )

    response = await admin_client.get("/api/v1/admin/resource-policies/catalog/k3s.server_image")

    assert response.status_code == 200
    assert response.json() == {"key": "k3s.server_image", "options": []}


@pytest.mark.asyncio
async def test_drover_policy_update_proxies_to_service(admin_client, monkeypatch):
    observed = {}

    async def remote(service_type, request, upstream_path):
        observed.update(service_type=service_type, upstream_path=upstream_path, body=await request.json())
        return JSONResponse({"key": "k3s.server_image", "resource_id": "image-1"})

    monkeypatch.setattr(admin_resource_policies, "proxy", remote)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=False, service_k3s_enabled=True),
    )

    response = await admin_client.put(
        "/api/v1/admin/resource-policies/k3s.server_image",
        json={"resource_id": "image-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"key": "k3s.server_image", "resource_id": "image-1"}
    assert observed == {
        "service_type": "drover",
        "upstream_path": "/v1/admin/resource-policies/k3s.server_image",
        "body": {"resource_id": "image-1"},
    }


@pytest.mark.asyncio
async def test_waygate_policy_catalog_proxies_without_backend_admin_connection(admin_client, monkeypatch):
    async def remote(service_type, _request, upstream_path):
        assert service_type == "waygate"
        assert upstream_path == "/v1/admin/resource-policies/catalog/waygate.image"
        return {"key": "waygate.image", "options": []}

    monkeypatch.setattr(
        admin_resource_policies,
        "get_admin_project_connection",
        lambda: pytest.fail("Waygate policy must not open the Afterglow admin connection"),
    )
    monkeypatch.setattr(admin_resource_policies, "get_json", remote)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=True, service_k3s_enabled=False),
    )

    response = await admin_client.get("/api/v1/admin/resource-policies/catalog/waygate.image")

    assert response.status_code == 200
    assert response.json() == {"key": "waygate.image", "options": []}


@pytest.mark.asyncio
async def test_waygate_policy_update_proxies_to_service(admin_client, monkeypatch):
    observed = {}

    async def remote(service_type, request, upstream_path):
        observed.update(service_type=service_type, upstream_path=upstream_path, body=await request.json())
        return JSONResponse({"key": "waygate.image", "resource_id": "image-1"})

    monkeypatch.setattr(admin_resource_policies, "proxy", remote)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=True, service_k3s_enabled=False),
    )

    response = await admin_client.put(
        "/api/v1/admin/resource-policies/waygate.image",
        json={"resource_id": "image-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"key": "waygate.image", "resource_id": "image-1"}
    assert observed == {
        "service_type": "waygate",
        "upstream_path": "/v1/admin/resource-policies/waygate.image",
        "body": {"resource_id": "image-1"},
    }


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
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=False, service_k3s_enabled=False),
    )

    response = await admin_client.get("/api/v1/admin/runtime-settings")
    assert response.status_code == 200
    assert response.json()[0]["key"] == "notion.sync_enabled"

    response = await admin_client.put("/api/v1/admin/runtime-settings/notion.sync_enabled", json={"value": False})
    assert response.status_code == 200
    assert response.json() == {"key": "notion.sync_enabled", "value": False}
    assert saved["key"] == "notion.sync_enabled"
    assert saved["value"] is False


@pytest.mark.asyncio
async def test_runtime_settings_merge_and_update_drover_k3s_version(admin_client, monkeypatch):
    async def local_settings():
        return [
            {"key": "notion.sync_enabled", "value": True, "state": "configured"},
            {"key": "k3s.version", "value": "stale-local", "state": "configured"},
        ]

    async def remote_json(service_type, _request, upstream_path):
        assert service_type == "drover"
        assert upstream_path == "/v1/admin/runtime-settings"
        return [{"key": "k3s.version", "value": "v1.31.5+k3s1", "state": "configured"}]

    observed = {}

    async def remote_proxy(service_type, request, upstream_path):
        observed.update(service_type=service_type, upstream_path=upstream_path, body=await request.json())
        return JSONResponse({"key": "k3s.version", "value": "v1.31.6+k3s1"})

    monkeypatch.setattr(admin_resource_policies.store, "list_runtime_settings", local_settings)
    monkeypatch.setattr(admin_resource_policies, "get_json", remote_json)
    monkeypatch.setattr(admin_resource_policies, "proxy", remote_proxy)
    monkeypatch.setattr(
        admin_resource_policies,
        "get_settings",
        lambda: SimpleNamespace(service_waygate_enabled=False, service_k3s_enabled=True),
    )

    response = await admin_client.get("/api/v1/admin/runtime-settings")
    assert response.status_code == 200
    assert response.json() == [
        {"key": "notion.sync_enabled", "value": True, "state": "configured"},
        {"key": "k3s.version", "value": "v1.31.5+k3s1", "state": "configured"},
    ]

    response = await admin_client.put(
        "/api/v1/admin/runtime-settings/k3s.version",
        json={"value": "v1.31.6+k3s1"},
    )
    assert response.status_code == 200
    assert response.json() == {"key": "k3s.version", "value": "v1.31.6+k3s1"}
    assert observed == {
        "service_type": "drover",
        "upstream_path": "/v1/admin/runtime-settings/k3s.version",
        "body": {"value": "v1.31.6+k3s1"},
    }


@pytest.mark.asyncio
async def test_runtime_settings_require_admin(non_admin_client):
    response = await non_admin_client.get("/api/v1/admin/runtime-settings")
    assert response.status_code == 403
