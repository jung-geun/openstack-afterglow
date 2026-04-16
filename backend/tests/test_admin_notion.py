"""admin_notion.py 엔드포인트 단위 테스트 (4개)."""

import pytest


@pytest.mark.asyncio
async def test_get_notion_config_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/notion/config")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_save_notion_config_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/notion/config", json={"api_key": "secret", "database_id": "db-1"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_notion_config_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/notion/config")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notion_test_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/notion/test")
    assert resp.status_code == 403
