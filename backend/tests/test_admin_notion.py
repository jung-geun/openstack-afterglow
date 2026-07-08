"""admin_notion.py 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_notion_config_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/notion/config")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_save_notion_config_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/v1/admin/notion/config", json={"api_key": "secret", "database_id": "db-1"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_notion_config_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/v1/admin/notion/config")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notion_test_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/v1/admin/notion/test")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notion_test_refreshes_gpu_catalog_before_mapping_calls(admin_client):
    instances = [
        {
            "name": "alias-vm",
            "instance_id": "inst-1",
            "status": "ACTIVE",
            "project_name": "proj",
            "flavor_name": "gpu.3060lhr_8c_16g",
            "vcpus": 8,
            "ram_gb": 16,
            "gpu_name": "RTX 3060 LHR",
            "gpu_count": 1,
            "gpu_spec_page_id": "page-3060",
            "fixed_ip": "",
            "floating_ip": "",
            "created_at": "2026-07-08T00:00:00Z",
            "compute_host": "",
            "user_page_id": "",
            "hypervisor_page_id": "",
        }
    ]
    call_order: list[str] = []

    async def _refresh():
        call_order.append("refresh")

    async def _collect_instance_data(**kwargs):
        call_order.append("collect")
        assert kwargs["gpu_name_to_page_id"] == {"RTX 3060 LHR": "page-3060"}
        return instances

    with (
        patch("app.database.is_db_available", return_value=True),
        patch(
            "app.services.notion_sync.get_notion_config",
            new=AsyncMock(
                return_value={
                    "api_key": "test-api-key",
                    "database_id": "test-db-id",
                    "users_database_id": "",
                    "hypervisors_database_id": "",
                    "gpu_spec_database_id": "gpu-spec-db-id",
                }
            ),
        ),
        patch("app.services.gpu_catalog.refresh_device_map_from_db", new=AsyncMock(side_effect=_refresh)) as refresh,
        patch(
            "app.api.identity.admin_gpu.get_gpu_spec_list",
            side_effect=lambda: call_order.append("gpu_specs") or [{"name": "RTX 3060 LHR"}],
        ),
        patch(
            "app.api.identity.admin_gpu.build_alias_to_device_name_map",
            side_effect=lambda: call_order.append("alias_map") or {"RTX-3060-LHR": "RTX 3060 LHR"},
        ),
        patch("app.api.identity.admin_notion.collect_instance_data", new=AsyncMock(side_effect=_collect_instance_data)),
        patch(
            "app.services.notion_sync.sync_gpu_specs_to_notion",
            new=AsyncMock(return_value={"created": 0, "updated": 0}),
        ),
        patch(
            "app.services.notion_sync.fetch_gpu_spec_page_ids_by_name",
            new=AsyncMock(return_value={"RTX 3060 LHR": "page-3060"}),
        ),
        patch("app.services.notion_sync.build_gpu_usage_by_gpu", return_value={}),
        patch(
            "app.services.notion_sync.sync_to_notion",
            new=AsyncMock(return_value={"created": 1, "updated": 0, "archived": 0}),
        ),
        patch("app.services.notion_sync.save_notion_config", new=AsyncMock()),
        patch("app.services.notion_sync.migrate_instance_db_to_korean", new=AsyncMock(return_value=False)),
    ):
        resp = await admin_client.post("/api/v1/admin/notion/test")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    refresh.assert_awaited_once()
    assert call_order.index("refresh") < call_order.index("gpu_specs")
    assert call_order.index("refresh") < call_order.index("collect")
    assert call_order.index("refresh") < call_order.index("alias_map")
