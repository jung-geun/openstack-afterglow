"""Waygate provisioning uses immutable database snapshots."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import waygate_provisioner


def _settings() -> SimpleNamespace:
    return SimpleNamespace(waygate_callback_base_url="https://backend.example.com")


def _record(*, floating_network_id: str | None = None) -> dict:
    snapshot = {
        "waygate.provider_network": {"id": "net-provider-1", "name": "Provider"},
        "waygate.image": {"id": "img-ubuntu-1", "name": "Ubuntu"},
        "waygate.flavor": {"id": "flavor-abc", "name": "CPU"},
    }
    if floating_network_id:
        snapshot["waygate.floating_network"] = {"id": floating_network_id, "name": "External"}
    return {
        "id": "server-1",
        "name": "waygate-gw-1",
        "listen_port": 51820,
        "provider_network_id": "net-provider-1",
        "image_id": "img-ubuntu-1",
        "flavor_id": "flavor-abc",
        "floating_network_id": floating_network_id,
        "resource_policy_snapshot": snapshot,
    }


@pytest.mark.asyncio
async def test_provision_uses_persisted_snapshot_without_fip():
    conn = MagicMock()
    conn.close = MagicMock()
    server = MagicMock(id="vm-123")
    conn.compute.create_server.return_value = server
    conn.compute.get_server.return_value = server

    with (
        patch("app.services.waygate_provisioner.get_settings", return_value=_settings()),
        patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
        patch("app.services.waygate_db.get_server_by_id", new=AsyncMock(return_value=_record())),
        patch("app.services.waygate_provisioner._ensure_wireguard_sg", return_value="sg-1"),
        patch("app.services.neutron.create_port", return_value={"id": "port-1"}) as create_port,
        patch("app.services.waygate_agent_auth.issue_report_token", new=AsyncMock(return_value="token")),
        patch("app.services.waygate_config.render_agent_userdata", return_value="userdata"),
        patch("app.services.waygate_db.update_server_status", new=AsyncMock()) as update_status,
        patch("app.services.waygate_provisioner._wait_for_active", new=AsyncMock()),
        patch("app.services.waygate_provisioner._extract_fixed_ip", return_value="10.0.0.5"),
    ):
        await waygate_provisioner.provision_waygate_server("project-1", "server-1", "user-1", "tester")

    create_port.assert_called_once_with(conn, "net-provider-1", "waygate-gw-1-port", ["sg-1"])
    kwargs = conn.compute.create_server.call_args.kwargs
    assert kwargs["image_id"] == "img-ubuntu-1"
    assert kwargs["flavor_id"] == "flavor-abc"
    assert "key_name" not in kwargs
    assert update_status.call_args_list[-1].kwargs["endpoint_ip"] == "10.0.0.5"


@pytest.mark.asyncio
async def test_provision_uses_optional_persisted_floating_network():
    conn = MagicMock()
    conn.close = MagicMock()
    server = MagicMock(id="vm-123")
    conn.compute.create_server.return_value = server
    conn.compute.get_server.return_value = server

    with (
        patch("app.services.waygate_provisioner.get_settings", return_value=_settings()),
        patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
        patch(
            "app.services.waygate_db.get_server_by_id",
            new=AsyncMock(return_value=_record(floating_network_id="net-external-1")),
        ),
        patch("app.services.waygate_provisioner._ensure_wireguard_sg", return_value="sg-1"),
        patch("app.services.neutron.create_port", return_value={"id": "port-1"}),
        patch("app.services.waygate_agent_auth.issue_report_token", new=AsyncMock(return_value="token")),
        patch("app.services.waygate_config.render_agent_userdata", return_value="userdata"),
        patch("app.services.waygate_db.update_server_status", new=AsyncMock()) as update_status,
        patch("app.services.waygate_provisioner._wait_for_active", new=AsyncMock()),
        patch("app.services.waygate_provisioner._extract_fixed_ip", return_value="10.0.0.5"),
        patch(
            "app.services.waygate_provisioner._allocate_new_fip", new=AsyncMock(return_value=("203.0.113.9", "fip-1"))
        ) as allocate_fip,
    ):
        await waygate_provisioner.provision_waygate_server("project-1", "server-1", "user-1", "tester")

    allocate_fip.assert_awaited_once_with(conn, "vm-123", "net-external-1")
    assert update_status.call_args_list[-1].kwargs["endpoint_ip"] == "203.0.113.9"


@pytest.mark.asyncio
async def test_provision_rejects_incomplete_snapshot_before_resource_creation():
    conn = MagicMock()
    conn.close = MagicMock()
    with (
        patch("app.services.waygate_provisioner.get_settings", return_value=_settings()),
        patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
        patch(
            "app.services.waygate_db.get_server_by_id",
            new=AsyncMock(return_value={"id": "server-1", "name": "waygate-gw-1", "listen_port": 51820}),
        ),
        patch("app.services.waygate_db.update_server_status", new=AsyncMock()) as update_status,
    ):
        await waygate_provisioner.provision_waygate_server("project-1", "server-1", "user-1", "tester")

    conn.compute.create_server.assert_not_called()
    assert update_status.call_args.args[1] == "ERROR"
