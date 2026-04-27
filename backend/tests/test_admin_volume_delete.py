"""admin 볼륨 삭제 엔드포인트 — force-delete 폴백 분기 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest
from openstack.exceptions import ResourceNotFound


def _make_volume(status: str, attachments: list | None = None) -> MagicMock:
    v = MagicMock()
    v.status = status
    v.attachments = attachments or []
    return v


@pytest.mark.asyncio
async def test_delete_volume_available_uses_normal_delete(admin_client, mock_conn):
    """available 상태 볼륨은 정상 delete 경로를 탄다."""
    mock_conn.block_storage.get_volume.return_value = _make_volume("available")

    with patch("app.services.cinder.force_delete_volume") as mock_force:
        resp = await admin_client.delete("/api/admin/volumes/vol-1")

    assert resp.status_code == 204
    mock_conn.block_storage.delete_volume.assert_called_once_with("vol-1", ignore_missing=True)
    mock_force.assert_not_called()


@pytest.mark.asyncio
async def test_delete_volume_error_deleting_uses_reset_then_delete(admin_client, mock_conn):
    """error_deleting 상태 볼륨은 reset_status → 일반 delete 경로로 정리된다."""
    mock_conn.block_storage.get_volume.return_value = _make_volume("error_deleting")

    with (
        patch("app.services.cinder.reset_volume_status") as mock_reset,
        patch("app.services.cinder.force_delete_volume") as mock_force,
    ):
        resp = await admin_client.delete("/api/admin/volumes/vol-2")

    assert resp.status_code == 204
    mock_reset.assert_called_once()
    mock_conn.block_storage.delete_volume.assert_called_once_with("vol-2", ignore_missing=True)
    mock_force.assert_not_called()


@pytest.mark.asyncio
async def test_delete_volume_error_uses_reset_then_delete(admin_client, mock_conn):
    """error 상태 볼륨도 reset_status → 일반 delete 경로로 정리된다."""
    mock_conn.block_storage.get_volume.return_value = _make_volume("error")

    with (
        patch("app.services.cinder.reset_volume_status"),
        patch("app.services.cinder.force_delete_volume") as mock_force,
    ):
        resp = await admin_client.delete("/api/admin/volumes/vol-3")

    assert resp.status_code == 204
    mock_conn.block_storage.delete_volume.assert_called_once()
    mock_force.assert_not_called()


@pytest.mark.asyncio
async def test_delete_volume_delete_fails_falls_back_to_force(admin_client, mock_conn):
    """reset 후 일반 delete가 실패하면 force_delete로 최종 폴백한다."""
    from openstack.exceptions import HttpException

    mock_conn.block_storage.get_volume.return_value = _make_volume("error_deleting")
    mock_conn.block_storage.delete_volume.side_effect = HttpException(http_status=400, message="still bad")

    with (
        patch("app.services.cinder.reset_volume_status"),
        patch("app.services.cinder.force_delete_volume") as mock_force,
    ):
        resp = await admin_client.delete("/api/admin/volumes/vol-fb")

    assert resp.status_code == 204
    mock_force.assert_called_once()


@pytest.mark.asyncio
async def test_delete_volume_already_gone_returns_204(admin_client, mock_conn):
    """Cinder에 볼륨이 이미 없으면 204로 idempotent 처리된다."""
    mock_conn.block_storage.get_volume.side_effect = ResourceNotFound()

    with patch("app.services.cinder.force_delete_volume") as mock_force:
        resp = await admin_client.delete("/api/admin/volumes/vol-gone")

    assert resp.status_code == 204
    mock_conn.block_storage.delete_volume.assert_not_called()
    mock_force.assert_not_called()


@pytest.mark.asyncio
async def test_delete_volume_deleting_uses_reset_then_delete(admin_client, mock_conn):
    """deleting 상태(stuck)도 reset_status → 일반 delete 경로로 진입한다."""
    mock_conn.block_storage.get_volume.return_value = _make_volume("deleting")

    with (
        patch("app.services.cinder.reset_volume_status") as mock_reset,
        patch("app.services.cinder.force_delete_volume") as mock_force,
    ):
        resp = await admin_client.delete("/api/admin/volumes/vol-stuck")

    assert resp.status_code == 204
    mock_reset.assert_called_once()
    mock_conn.block_storage.delete_volume.assert_called_once()
    mock_force.assert_not_called()


@pytest.mark.asyncio
async def test_delete_volume_in_use_returns_400(admin_client, mock_conn):
    """in-use 상태 볼륨은 force-delete 폴백 없이 400을 반환한다."""
    from openstack.exceptions import HttpException

    mock_conn.block_storage.get_volume.return_value = _make_volume("in-use", attachments=[{"id": "att-1"}])
    mock_conn.block_storage.delete_volume.side_effect = HttpException(http_status=400, message="Invalid volume")

    with patch("app.services.cinder.force_delete_volume") as mock_force:
        resp = await admin_client.delete("/api/admin/volumes/vol-attached")

    assert resp.status_code == 400
    mock_force.assert_not_called()


# ── force-delete 엔드포인트 테스트 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_force_delete_normal_status_succeeds(admin_client, mock_conn):
    """available 상태 볼륨도 force-delete 엔드포인트로 삭제 가능하다."""
    mock_conn.block_storage.get_volume.return_value = _make_volume("available")

    with (
        patch("app.services.cinder.reset_volume_status"),
        patch("app.services.cinder.force_delete_volume") as mock_force,
    ):
        resp = await admin_client.post("/api/admin/volumes/vol-x/force-delete")

    assert resp.status_code == 204
    mock_conn.block_storage.delete_volume.assert_called_once()
    mock_force.assert_not_called()


@pytest.mark.asyncio
async def test_force_delete_attached_returns_409(admin_client, mock_conn):
    """attached 볼륨은 강제 삭제 시 409를 반환한다."""
    mock_conn.block_storage.get_volume.return_value = _make_volume("in-use", attachments=[{"id": "a"}])

    resp = await admin_client.post("/api/admin/volumes/vol-att/force-delete")

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_force_delete_already_gone_returns_204(admin_client, mock_conn):
    """이미 없는 볼륨에 force-delete 요청 시 204로 idempotent 처리된다."""
    mock_conn.block_storage.get_volume.side_effect = ResourceNotFound()

    resp = await admin_client.post("/api/admin/volumes/vol-gone/force-delete")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_force_delete_volume_requires_admin(non_admin_client):
    """비admin 사용자는 force-delete 엔드포인트에 접근할 수 없다."""
    resp = await non_admin_client.post("/api/admin/volumes/vol-1/force-delete")

    assert resp.status_code == 403
