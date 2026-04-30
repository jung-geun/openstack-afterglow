"""볼륨 transfer 자동 detach 단위 테스트.

A4: volume transfer 생성 전 VM attachment 자동 detach + 상태 대기
"""

from unittest.mock import AsyncMock, patch

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
    """attachments 없는 볼륨은 detach 없이 바로 transfer 생성."""
    with (
        patch("app.api.storage.volumes.cinder.get_volume", return_value=_make_volume()),
        patch("app.api.storage.volumes.cinder.create_volume_transfer", return_value=_TRANSFER_RESULT),
        patch("app.api.storage.volumes.nova.detach_volume") as mock_detach,
    ):
        resp = await client.post("/api/volumes/vol-1/transfer", json={})
    assert resp.status_code == 201
    mock_detach.assert_not_called()


@pytest.mark.asyncio
async def test_transfer_auto_detaches_attached_vm(client):
    """attached 볼륨: detach 호출 후 available 확인 → transfer 생성."""
    attached = _make_volume("in-use", attachments=[{"server_id": "srv-1", "attachment_id": "att-1"}])
    available = _make_volume("available")

    with (
        patch("app.api.storage.volumes.cinder.get_volume", side_effect=[attached, available]),
        patch("app.api.storage.volumes.nova.detach_volume") as mock_detach,
        patch("app.api.storage.volumes.cinder.create_volume_transfer", return_value=_TRANSFER_RESULT),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/volumes/vol-1/transfer", json={})
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
    available = _make_volume("available")

    with (
        patch("app.api.storage.volumes.cinder.get_volume", side_effect=[attached, available]),
        patch("app.api.storage.volumes.nova.detach_volume") as mock_detach,
        patch("app.api.storage.volumes.cinder.create_volume_transfer", return_value=_TRANSFER_RESULT),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/volumes/vol-1/transfer", json={})
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
        resp = await client.post("/api/volumes/vol-1/transfer", json={})
    assert resp.status_code == 409
    assert "detach 실패" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_volume_not_found_returns_404(client):
    """볼륨 미존재 시 404 반환."""
    with patch("app.api.storage.volumes.cinder.get_volume", side_effect=RuntimeError("not found")):
        resp = await client.post("/api/volumes/vol-1/transfer", json={})
    assert resp.status_code == 404
