"""Notion 다중 타겟 + dedup 테스트."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_token_info


# ---------------------------------------------------------------------------
# dedup: sync_to_notion._upsert에서 동일 데이터면 PATCH 스킵
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_dedup_skips_patch_on_same_hash():
    """동일 properties hash가 Redis에 캐시되어 있으면 PATCH를 생략한다."""
    from app.services.notion_sync import sync_to_notion

    # 인스턴스 데이터 하나
    instances = [
        {
            "name": "test-vm",
            "instance_id": "inst-001",
            "status": "ACTIVE",
            "project_name": "proj",
            "flavor_name": "m1.small",
            "vcpus": 2,
            "ram_gb": 4,
            "gpu_name": "",
            "gpu_count": 0,
            "gpu_spec_page_id": "",
            "fixed_ip": "10.0.0.1",
            "floating_ip": "",
            "created_at": "2024-01-01T00:00:00Z",
            "compute_host": "host1",
            "user_page_id": "",
            "hypervisor_page_id": "",
        }
    ]

    mock_schema = {
        "Name": {"type": "title"},
        "인스턴스 ID": {"type": "rich_text"},
    }
    mock_pages = [
        {
            "id": "page-001",
            "properties": {
                "인스턴스 ID": {"type": "rich_text", "rich_text": [{"plain_text": "inst-001"}]},
                "Name": {"type": "title", "title": [{"plain_text": "test-vm"}]},
            },
        }
    ]

    # 같은 hash를 Redis에서 반환 → skip
    import hashlib

    # properties를 미리 계산해서 같은 hash를 주입
    from app.services.notion_sync import _build_instance_properties, _find_title_prop

    title_prop = _find_title_prop(mock_schema)
    props = _build_instance_properties(mock_schema, title_prop, instances[0])
    prop_hash = hashlib.sha256(json.dumps(props, sort_keys=True).encode()).hexdigest()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=prop_hash)  # 캐시된 hash와 동일

    mock_httpx_client = AsyncMock()
    mock_httpx_client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"properties": mock_schema}))
    mock_httpx_client.post = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"results": mock_pages, "has_more": False})
    )
    mock_httpx_client.patch = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.cache._get_redis", AsyncMock(return_value=mock_redis)),
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
    ):
        stats = await sync_to_notion("api-key-123", "db-001", instances)

    # PATCH는 호출되지 않아야 한다
    mock_httpx_client.patch.assert_not_called()
    assert stats["skipped"] == 1
    assert stats["updated"] == 0


@pytest.mark.asyncio
async def test_sync_dedup_patches_on_hash_mismatch():
    """Redis hash가 다르면 PATCH를 호출하고 새 hash를 저장한다."""
    from app.services.notion_sync import sync_to_notion

    instances = [
        {
            "name": "test-vm",
            "instance_id": "inst-001",
            "status": "SHUTOFF",  # 상태 변경됨
            "project_name": "proj",
            "flavor_name": "m1.small",
            "vcpus": 2,
            "ram_gb": 4,
            "gpu_name": "",
            "gpu_count": 0,
            "gpu_spec_page_id": "",
            "fixed_ip": "10.0.0.1",
            "floating_ip": "",
            "created_at": "2024-01-01T00:00:00Z",
            "compute_host": "host1",
            "user_page_id": "",
            "hypervisor_page_id": "",
        }
    ]

    mock_schema = {
        "Name": {"type": "title"},
        "인스턴스 ID": {"type": "rich_text"},
        "상태": {"type": "select"},
    }
    mock_pages = [
        {
            "id": "page-001",
            "properties": {
                "인스턴스 ID": {"type": "rich_text", "rich_text": [{"plain_text": "inst-001"}]},
                "Name": {"type": "title", "title": [{"plain_text": "test-vm"}]},
            },
        }
    ]

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="old-hash-different")  # 다른 hash
    mock_redis.set = AsyncMock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"properties": mock_schema}))
    mock_httpx_client.post = AsyncMock(
        return_value=MagicMock(status_code=200, json=lambda: {"results": mock_pages, "has_more": False})
    )
    mock_httpx_client.patch = AsyncMock(return_value=MagicMock(status_code=200))
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.cache._get_redis", AsyncMock(return_value=mock_redis)),
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
    ):
        stats = await sync_to_notion("api-key-123", "db-001", instances)

    # PATCH가 1회 호출되어야 한다
    mock_httpx_client.patch.assert_called_once()
    assert stats["updated"] == 1
    assert stats["skipped"] == 0
    # 새 hash가 Redis에 저장되어야 한다
    mock_redis.set.assert_called_once()


@pytest.mark.asyncio
async def test_sync_new_instance_always_posts():
    """page_map에 없는 인스턴스는 dedup 없이 항상 POST한다."""
    from app.services.notion_sync import sync_to_notion

    instances = [
        {
            "name": "new-vm",
            "instance_id": "inst-new",
            "status": "ACTIVE",
            "project_name": "proj",
            "flavor_name": "m1.medium",
            "vcpus": 4,
            "ram_gb": 8,
            "gpu_name": "",
            "gpu_count": 0,
            "gpu_spec_page_id": "",
            "fixed_ip": "10.0.0.2",
            "floating_ip": "",
            "created_at": "2024-06-01T00:00:00Z",
            "compute_host": "host1",
            "user_page_id": "",
            "hypervisor_page_id": "",
        }
    ]

    mock_schema = {"Name": {"type": "title"}, "인스턴스 ID": {"type": "rich_text"}}
    # DB에 페이지 없음
    mock_pages: list = []

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    mock_httpx_client = AsyncMock()
    mock_httpx_client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"properties": mock_schema}))
    mock_httpx_client.post = AsyncMock(
        side_effect=[
            MagicMock(status_code=200, json=lambda: {"results": mock_pages, "has_more": False}),  # query
            MagicMock(status_code=200),  # page create
        ]
    )
    mock_httpx_client.patch = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.cache._get_redis", AsyncMock(return_value=mock_redis)),
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
    ):
        stats = await sync_to_notion("api-key-123", "db-001", instances)

    assert stats["created"] == 1
    assert stats["skipped"] == 0
    # PATCH는 호출되지 않아야 한다 (새 페이지는 POST)
    mock_httpx_client.patch.assert_not_called()


# ---------------------------------------------------------------------------
# 다중 타겟: API 엔드포인트 CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_notion_targets_empty(admin_client):
    """NotionTarget이 없으면 빈 배열을 반환한다."""
    with patch("app.services.notion_sync.list_notion_targets", AsyncMock(return_value=[])):
        resp = await admin_client.get("/api/admin/notion/targets")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_notion_targets_returns_masked_keys(admin_client):
    """API key는 마스킹되어 반환된다."""
    fake_targets = [
        {
            "id": 1,
            "label": "운영팀",
            "api_key": "ntn_****(masked)****",
            "database_id": "db-abc",
            "users_database_id": "",
            "hypervisors_database_id": "",
            "gpu_spec_database_id": "",
            "enabled": True,
            "interval_minutes": 5,
            "last_sync": None,
            "hypervisors_last_sync": None,
            "gpu_spec_last_sync": None,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
    ]
    with patch("app.services.notion_sync.list_notion_targets", AsyncMock(return_value=fake_targets)):
        resp = await admin_client.get("/api/admin/notion/targets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "masked" in data[0]["api_key"] or "****" in data[0]["api_key"]


@pytest.mark.asyncio
async def test_delete_notion_target_not_found(admin_client):
    """존재하지 않는 타겟 삭제 시 404를 반환한다."""
    with patch("app.services.notion_sync.delete_notion_target", AsyncMock(return_value=False)):
        resp = await admin_client.delete("/api/admin/notion/targets/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_notion_target_success(admin_client):
    """정상 삭제 시 200과 ok 메시지를 반환한다."""
    with patch("app.services.notion_sync.delete_notion_target", AsyncMock(return_value=True)):
        resp = await admin_client.delete("/api/admin/notion/targets/1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_update_notion_target_not_found(admin_client):
    """존재하지 않는 타겟 수정 시 404를 반환한다."""
    with (
        patch("app.services.notion_sync.get_notion_target", AsyncMock(return_value=None)),
        patch("app.services.notion_sync.update_notion_target", AsyncMock(return_value=None)),
    ):
        resp = await admin_client.patch("/api/admin/notion/targets/999", json={"label": "new"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_notion_target_invalid_interval(admin_client):
    """interval_minutes 범위 초과 시 400을 반환한다."""
    resp = await admin_client.patch("/api/admin/notion/targets/1", json={"interval_minutes": 9999})
    assert resp.status_code == 400
