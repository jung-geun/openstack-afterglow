"""활동 로그 API 및 서비스 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_profile_activity_returns_list(client):
    """일반 사용자 본인 활동 조회 — 200 + 빈 리스트."""
    with patch(
        "app.api.identity.profile_activity.svc.list_for_user",
        new=AsyncMock(return_value=[]),
    ):
        r = await client.get("/api/v1/profile/activity")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_profile_activity_with_results(client):
    """결과가 있을 때 목록 반환."""
    fake_row = {
        "id": 1,
        "created_at": "2025-01-01T00:00:00+00:00",
        "project_id": "p1",
        "user_id": "u1",
        "username": "user1",
        "resource_type": "instance",
        "resource_id": "inst-1",
        "resource_name": "web-server",
        "action": "instance.create",
        "status": "success",
        "error_message": None,
        "extra": None,
    }
    with patch(
        "app.api.identity.profile_activity.svc.list_for_user",
        new=AsyncMock(return_value=[fake_row]),
    ):
        r = await client.get("/api/v1/profile/activity")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["action"] == "instance.create"
    assert data[0]["status"] == "success"


@pytest.mark.asyncio
async def test_admin_activity_requires_admin(client):
    """일반 사용자는 admin activity API 에 접근 불가."""
    r = await client.get("/api/v1/admin/projects/p1/activity")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_activity_ok_for_admin(admin_client):
    """admin 사용자는 프로젝트 활동 조회 가능."""
    with patch(
        "app.api.identity.admin_activity.svc.list_for_project",
        new=AsyncMock(return_value=[]),
    ):
        r = await admin_client.get("/api/v1/admin/projects/p1/activity")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_admin_activity_query_params(admin_client):
    """query 파라미터가 서비스 함수에 전달된다."""
    mock_fn = AsyncMock(return_value=[])
    with patch("app.api.identity.admin_activity.svc.list_for_project", new=mock_fn):
        await admin_client.get(
            "/api/v1/admin/projects/my-project/activity?limit=10&resource_type=volume&action=volume.create&user_id=u1"
        )
    mock_fn.assert_called_once_with(
        "my-project",
        limit=10,
        before_id=None,
        resource_type="volume",
        action="volume.create",
        user_id="u1",
    )


@pytest.mark.asyncio
async def test_record_skipped_when_db_unavailable():
    """DB 미가용 시 record 가 예외 없이 skip."""
    from app.services import activity as svc

    with patch("app.services.activity.is_db_available", return_value=False):
        await svc.record(
            project_id="p",
            user_id="u",
            username="x",
            resource_type="instance",
            action="instance.create",
            status="success",
        )


@pytest.mark.asyncio
async def test_record_skipped_when_factory_none():
    """session_factory 가 None 이어도 예외 없이 skip."""
    from app.services import activity as svc

    with (
        patch("app.services.activity.is_db_available", return_value=True),
        patch("app.services.activity.get_session_factory", return_value=None),
    ):
        await svc.record(
            project_id="p",
            user_id="u",
            username="x",
            resource_type="instance",
            action="instance.create",
            status="success",
        )


@pytest.mark.asyncio
async def test_record_writes_row_when_db_available():
    """DB 가용 시 ActivityLog row 를 session.add 한다."""
    from app.services import activity as svc

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    with (
        patch("app.services.activity.is_db_available", return_value=True),
        patch("app.services.activity.get_session_factory", return_value=mock_factory),
    ):
        await svc.record(
            project_id="p",
            user_id="u",
            username="testuser",
            resource_type="volume",
            action="volume.create",
            status="success",
            resource_id="vol-123",
            resource_name="my-volume",
        )

    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert added.resource_type == "volume"
    assert added.action == "volume.create"
    assert added.status == "success"
    assert added.resource_name == "my-volume"
