"""볼륨 transfer 자동 detach + rollback 단위 테스트.

A4: volume transfer 생성 전 VM attachment 자동 detach + 상태 대기 + 실패 시 rollback
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.storage import VolumeInfo


def _make_volume(status: str = "available", attachments: list | None = None) -> VolumeInfo:
    return VolumeInfo(
        id="vol-1",
        name="test-vol",
        status=status,
        size=10,
        volume_type=None,
        attachments=attachments or [],
    )


_TRANSFER_RESULT = {
    "id": "tr-1",
    "name": "transfer-1",
    "volume_id": "vol-1",
    "auth_key": "secret-key",
    "created_at": None,
}


@pytest.mark.asyncio
async def test_transfer_no_attachments_skips_detach(client):
    """attachments 없는 볼륨은 detach/wait 없이 바로 transfer 생성."""
    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=_make_volume()),
        patch("app.api.storage.volumes.cinder.create_volume_transfer", return_value=_TRANSFER_RESULT),
        patch("app.api.storage.volumes.nova.detach_volume") as mock_detach,
        patch("app.api.storage.volumes.cinder.wait_volume_available") as mock_wait,
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 201
    mock_detach.assert_not_called()
    mock_wait.assert_not_called()


@pytest.mark.asyncio
async def test_transfer_auto_detaches_attached_vm(client):
    """attached 볼륨: detach 호출 후 available 대기 후 transfer 생성."""
    attached = _make_volume("in-use", attachments=[{"server_id": "srv-1", "attachment_id": "att-1"}])

    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=attached),
        patch("app.api.storage.volumes.nova.detach_volume") as mock_detach,
        patch("app.api.storage.volumes.cinder.wait_volume_available", return_value=_make_volume("available")),
        patch("app.api.storage.volumes.cinder.create_volume_transfer", return_value=_TRANSFER_RESULT),
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 201
    mock_detach.assert_called_once()
    assert resp.json()["auth_key"] == "secret-key"


@pytest.mark.asyncio
async def test_transfer_detaches_multiple_attachments(client):
    """여러 VM에 연결된 볼륨: 각 attachment마다 detach 호출."""
    attached = _make_volume(
        "in-use",
        attachments=[
            {"server_id": "srv-1", "attachment_id": "att-1"},
            {"server_id": "srv-2", "attachment_id": "att-2"},
        ],
    )

    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=attached),
        patch("app.api.storage.volumes.nova.detach_volume") as mock_detach,
        patch("app.api.storage.volumes.cinder.wait_volume_available", return_value=_make_volume("available")),
        patch("app.api.storage.volumes.cinder.create_volume_transfer", return_value=_TRANSFER_RESULT),
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 201
    assert mock_detach.call_count == 2


@pytest.mark.asyncio
async def test_transfer_detach_failure_returns_409(client):
    """detach 실패 시 409 반환."""
    attached = _make_volume("in-use", attachments=[{"server_id": "srv-1", "attachment_id": "att-1"}])

    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=attached),
        patch("app.api.storage.volumes.nova.detach_volume", side_effect=RuntimeError("detach error")),
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 409
    assert "detach 실패" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_volume_not_found_returns_404(client):
    """볼륨 미존재 시 404 반환."""
    with patch("app.api.storage.volumes.cinder.get_volume", side_effect=RuntimeError("not found")):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_transfer_wait_timeout_returns_409(client):
    """detach 후 available 대기 실패(timeout) 시 409 반환."""
    attached = _make_volume("in-use", attachments=[{"server_id": "srv-1", "attachment_id": "att-1"}])

    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=attached),
        patch("app.api.storage.volumes.nova.detach_volume"),
        patch(
            "app.api.storage.volumes.cinder.wait_volume_available",
            side_effect=RuntimeError("timeout"),
        ),
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 409
    assert "대기 시간 초과" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_creation_failure_rollbacks_attach(client):
    """transfer 생성 실패 시 detach했던 서버에 볼륨을 다시 attach(rollback)한다."""
    attached = _make_volume("in-use", attachments=[{"server_id": "srv-1", "attachment_id": "att-1"}])

    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=attached),
        patch("app.api.storage.volumes.nova.detach_volume"),
        patch("app.api.storage.volumes.cinder.wait_volume_available", return_value=_make_volume("available")),
        patch(
            "app.api.storage.volumes.cinder.create_volume_transfer",
            side_effect=RuntimeError("transfer API error"),
        ),
        patch("app.api.storage.volumes.nova.attach_volume") as mock_reattach,
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 500
    mock_reattach.assert_called_once()
    assert mock_reattach.call_args.args[1] == "srv-1"


@pytest.mark.asyncio
async def test_transfer_rollback_multiple_servers(client):
    """여러 서버 detach 후 transfer 실패 시 모든 서버에 rollback attach."""
    attached = _make_volume(
        "in-use",
        attachments=[
            {"server_id": "srv-A", "attachment_id": "att-A"},
            {"server_id": "srv-B", "attachment_id": "att-B"},
        ],
    )

    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=attached),
        patch("app.api.storage.volumes.nova.detach_volume"),
        patch("app.api.storage.volumes.cinder.wait_volume_available", return_value=_make_volume("available")),
        patch(
            "app.api.storage.volumes.cinder.create_volume_transfer",
            side_effect=RuntimeError("transfer API error"),
        ),
        patch("app.api.storage.volumes.nova.attach_volume") as mock_reattach,
    ):
        resp = await client.post("/api/v1/volumes/vol-1/transfer", json={})
    assert resp.status_code == 500
    assert mock_reattach.call_count == 2


# ---------------------------------------------------------------------------
# cinder.wait_volume_available 서비스 함수 단위테스트
# ---------------------------------------------------------------------------


def test_wait_volume_available_returns_volume_info():
    """wait_volume_available: wait_for_status 성공 시 VolumeInfo 반환."""
    from app.services.cinder import wait_volume_available

    conn = MagicMock()
    mock_vol = MagicMock()
    mock_vol.id = "vol-x"
    mock_vol.name = "test"
    mock_vol.status = "available"
    mock_vol.size = 20
    mock_vol.volume_type = None
    mock_vol.attachments = []

    conn.block_storage.get_volume.return_value = mock_vol
    conn.block_storage.wait_for_status.return_value = mock_vol

    result = wait_volume_available(conn, "vol-x", timeout=10)
    assert result.status == "available"
    conn.block_storage.wait_for_status.assert_called_once_with(mock_vol, status="available", wait=10)
