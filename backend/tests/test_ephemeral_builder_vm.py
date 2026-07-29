"""Ephemeral Builder VM snapshot and cleanup regression tests."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _server(server_id: str = "srv-abc", fixed_ip: str = "10.0.0.5") -> MagicMock:
    result = MagicMock()
    result.id = server_id
    result.status = "ACTIVE"
    result.addresses = {"internal": [{"addr": fixed_ip, "OS-EXT-IPS:type": "fixed"}]}
    return result


def test_extract_fixed_ip_ignores_floating_addresses():
    from app.services.builder_vm import _extract_fixed_ip

    server = MagicMock(addresses={"net": [{"addr": "1.2.3.4", "OS-EXT-IPS:type": "floating"}]})
    assert _extract_fixed_ip(server) is None


@pytest.mark.asyncio
async def test_create_requires_explicit_snapshot_resources():
    from app.services.builder_vm import create_ephemeral_vm

    with pytest.raises(ValueError, match="image_id"):
        await create_ephemeral_vm(MagicMock(), image_id="", flavor_id="flavor", network_id="network")


@pytest.mark.asyncio
async def test_create_uses_explicit_resources_and_one_use_keypair():
    from app.services.builder_vm import EphemeralBuilderVM, create_ephemeral_vm

    connection = MagicMock()
    connection.compute.create_server.return_value = _server("srv-xyz", "10.0.0.7")
    connection.compute.get_server.return_value = _server("srv-xyz", "10.0.0.7")
    settings = MagicMock(builder_ssh_user="ubuntu")
    with (
        patch("app.services.builder_vm.get_settings", return_value=settings),
        patch(
            "app.services.builder_vm._create_one_use_keypair",
            new_callable=AsyncMock,
            return_value=("one-use-key", "/tmp/one-use-key"),
        ),
        patch("app.services.builder_vm._wait_for_active", new_callable=AsyncMock),
        patch("app.services.builder_vm._wait_for_ssh", new_callable=AsyncMock),
        patch("app.services.builder_vm._wait_for_cloud_init", new_callable=AsyncMock),
    ):
        vm = await create_ephemeral_vm(
            connection,
            image_id="snapshot-image",
            flavor_id="snapshot-flavor",
            network_id="snapshot-network",
        )

    assert isinstance(vm, EphemeralBuilderVM)
    assert vm.server_id == "srv-xyz"
    assert vm.keypair_name == "one-use-key"
    kwargs = connection.compute.create_server.call_args.kwargs
    assert kwargs["image_id"] == "snapshot-image"
    assert kwargs["flavor_id"] == "snapshot-flavor"
    assert kwargs["networks"] == [{"uuid": "snapshot-network"}]
    assert kwargs["key_name"] == "one-use-key"


@pytest.mark.asyncio
async def test_delete_cleans_fip_server_keypair_and_local_private_key(tmp_path):
    from app.services.builder_vm import delete_ephemeral_vm

    key_path = tmp_path / "ephemeral.key"
    key_path.write_text("private")
    connection = MagicMock()

    await delete_ephemeral_vm(
        connection,
        server_id="srv-del",
        fip_id="fip-del",
        keypair_name="one-use-key",
        key_path=str(key_path),
    )

    connection.network.delete_ip.assert_called_once_with("fip-del")
    connection.compute.delete_server.assert_called_once_with("srv-del")
    connection.compute.delete_keypair.assert_called_once_with("one-use-key")
    assert not os.path.exists(key_path)
