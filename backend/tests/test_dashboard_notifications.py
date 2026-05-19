"""Phase 51d — 사용자용 /api/dashboard/notifications endpoint 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest


def _patch_redis():
    from app.services import cache as cache_mod

    fake = AsyncMock()
    fake.get.return_value = None
    fake.setex.return_value = None
    fake.delete.return_value = None
    return patch.object(cache_mod, "_get_client", return_value=fake)


@pytest.mark.asyncio
async def test_notifications_empty_when_no_errors(client, mock_conn):
    """ERROR 인스턴스 없으면 빈 알림 목록 반환."""
    from app.services import nova as nova_svc

    with _patch_redis(), patch.object(nova_svc, "list_servers", return_value=[]):
        resp = await client.get("/api/dashboard/notifications")

    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data
    assert data["notifications"] == []


@pytest.mark.asyncio
async def test_notifications_error_instance_triggers_alert(client, mock_conn):
    """ERROR 인스턴스가 있으면 danger 알림 반환."""
    from app.services import nova as nova_svc

    error_server = type(
        "S", (), {"id": "s1", "status": "ERROR", "flavor_id": None, "flavor_name": "m1.small"}
    )()

    with _patch_redis(), patch.object(nova_svc, "list_servers", return_value=[error_server]):
        resp = await client.get("/api/dashboard/notifications")

    assert resp.status_code == 200
    data = resp.json()
    notifications = data["notifications"]
    assert len(notifications) == 1
    assert notifications[0]["severity"] == "danger"
    assert notifications[0]["count"] == 1
    assert "오류 상태 인스턴스" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_notifications_project_scoped(client, mock_conn):
    """project-scoped connection 사용 — 정상 인스턴스는 알림 없음."""
    from app.services import nova as nova_svc

    active_server = type(
        "S", (), {"id": "s2", "status": "ACTIVE", "flavor_id": None, "flavor_name": "m1.small"}
    )()

    with _patch_redis(), patch.object(nova_svc, "list_servers", return_value=[active_server]):
        resp = await client.get("/api/dashboard/notifications")

    assert resp.status_code == 200
    assert resp.json()["notifications"] == []
