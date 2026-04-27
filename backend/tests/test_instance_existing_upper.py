"""existing_upper_volume_id 인스턴스 생성 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.compute import InstanceInfo


def _make_vol(status: str = "available"):
    v = MagicMock()
    v.id = "vol-existing"
    v.status = status
    return v


def _make_server():
    return InstanceInfo(
        id="srv-1",
        name="test-vm",
        status="BUILD",
        image_id="img-1",
        image_name="ubuntu-22.04",
        flavor_id="flavor-1",
        flavor_name="m1.small",
        ip_addresses=[],
        created_at="2024-01-01T00:00:00Z",
        metadata={},
        union_libraries=[],
        union_strategy=None,
        union_share_ids=[],
        union_upper_volume_id=None,
        key_name=None,
        user_id="test-user-123",
    )


BASE_PAYLOAD = {
    "name": "test-vm",
    "image_id": "img-1",
    "flavor_id": "flavor-1",
    "network_id": "net-1",
    "existing_upper_volume_id": "vol-existing",
}

_COMMON_PATCHES = [
    ("app.api.compute.instances.lib_svc.resolve_with_deps", []),
    ("app.api.compute.instances.cinder.create_volume_from_image", _make_vol()),
    ("app.api.compute.instances.cinder.rename_volume", None),
    ("app.api.compute.instances.nova.list_flavors", []),
    ("app.api.compute.instances.nova.create_server", _make_server()),
    ("app.api.compute.instances.neutron.list_networks", []),
    ("app.api.compute.instances.cloudinit.generate_userdata", ""),
]


@pytest.mark.asyncio
async def test_create_instance_existing_upper_skips_create_empty_volume(client, mock_conn):
    """existing_upper_volume_id 지정 시 create_empty_volume을 호출하지 않는다."""
    mock_conn.compute.create_volume_attachment = MagicMock(return_value=None)

    with (
        patch("app.api.compute.instances.lib_svc.resolve_with_deps", return_value=[]),
        patch("app.api.compute.instances._prepare_dynamic_file_storage", return_value={}),
        patch("app.api.compute.instances.cinder.create_volume_from_image", return_value=_make_vol()),
        patch("app.api.compute.instances.cinder.rename_volume", return_value=None),
        patch("app.api.compute.instances.cinder.get_volume", return_value=_make_vol("available")) as mock_get,
        patch("app.api.compute.instances.cinder.create_empty_volume") as mock_create_empty,
        patch("app.api.compute.instances.nova.list_flavors", return_value=[]),
        patch("app.api.compute.instances.nova.create_server", return_value=_make_server()),
        patch("app.api.compute.instances.neutron.list_networks", return_value=[]),
        patch("app.api.compute.instances.cloudinit.generate_userdata", return_value=""),
    ):
        resp = await client.post("/api/instances", json=BASE_PAYLOAD)

    assert resp.status_code == 201
    mock_create_empty.assert_not_called()
    mock_get.assert_called_once_with(mock_conn, "vol-existing")


@pytest.mark.asyncio
async def test_create_instance_existing_upper_in_use_returns_400(client, mock_conn):
    """existing_upper_volume_id가 in-use 상태면 400을 반환한다."""
    with (
        patch("app.api.compute.instances.lib_svc.resolve_with_deps", return_value=[]),
        patch("app.api.compute.instances._prepare_dynamic_file_storage", return_value={}),
        patch("app.api.compute.instances.cinder.create_volume_from_image", return_value=_make_vol()),
        patch("app.api.compute.instances.cinder.rename_volume", return_value=None),
        patch("app.api.compute.instances.cinder.get_volume", return_value=_make_vol("in-use")),
        patch("app.api.compute.instances.cinder.create_empty_volume") as mock_create_empty,
    ):
        resp = await client.post("/api/instances", json=BASE_PAYLOAD)

    assert resp.status_code == 400
    mock_create_empty.assert_not_called()
