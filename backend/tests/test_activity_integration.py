"""활동 로그 통합 테스트 — 볼륨 생성 시 record() 호출 및 admin 필터링 검증."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def make_mock_volume(vol_id: str = "vol-1", name: str = "test-vol", status: str = "available"):
    from app.models.storage import VolumeInfo

    return VolumeInfo(id=vol_id, name=name, status=status, size=10, volume_type=None, attachments=[])


@pytest.mark.asyncio
async def test_volume_create_records_activity(client):
    """볼륨 생성 성공 시 record() 가 resource_type='volume', action='volume.create', status='success' 로 호출된다."""
    mock_record = AsyncMock()
    with (
        patch("app.api.storage.volumes.cinder.create_empty_volume", return_value=make_mock_volume("vol-new", "my-vol")),
        patch("app.api.storage.volumes.invalidate", new=AsyncMock()),
        patch("app.api.common.activity_recorder.record", new=mock_record),
    ):
        resp = await client.post("/api/v1/volumes", json={"name": "my-vol", "size_gb": 10})

    assert resp.status_code == 201
    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["resource_type"] == "volume"
    assert call_kwargs["action"] == "volume.create"
    assert call_kwargs["status"] == "success"


@pytest.mark.asyncio
async def test_volume_create_failed_records_failed_status(client):
    """볼륨 생성 실패 시 record() 가 status='failed', error_message 가 None 이 아닌 값으로 호출된다."""
    mock_record = AsyncMock()
    with (
        patch("app.api.storage.volumes.cinder.create_empty_volume", side_effect=Exception("Cinder 오류")),
        patch("app.api.common.activity_recorder.record", new=mock_record),
    ):
        resp = await client.post("/api/v1/volumes", json={"name": "bad-vol", "size_gb": 10})

    assert resp.status_code == 500
    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["resource_type"] == "volume"
    assert call_kwargs["action"] == "volume.create"
    assert call_kwargs["status"] == "failed"
    assert call_kwargs.get("error_message") is not None


@pytest.mark.asyncio
async def test_admin_activity_endpoint_filters(admin_client):
    """GET /api/admin/projects/{id}/activity?resource_type=volume 가 list_for_project 에 resource_type='volume' 을 전달한다."""
    mock_fn = AsyncMock(return_value=[])
    with patch("app.api.identity.admin_activity.svc.list_for_project", new=mock_fn):
        resp = await admin_client.get("/api/v1/admin/projects/test-project/activity?resource_type=volume")

    assert resp.status_code == 200
    mock_fn.assert_called_once()
    call_kwargs = mock_fn.call_args.kwargs
    assert call_kwargs.get("resource_type") == "volume"
