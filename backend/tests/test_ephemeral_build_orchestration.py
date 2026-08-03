"""Ephemeral build orchestration tests with persisted resource snapshots."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_TOKEN = "aaaa1111bbbb2222cccc3333dddd4444"
_SUCCESS_LINE = f"::AFTERGLOW::SUCCESS::{_TOKEN}"
_FAILURE_LINE = f"::AFTERGLOW::FAILURE::{_TOKEN}::rc=1"


class _FakeRecipe:
    library_id = "python311"
    share_proto = "NFS"
    share_size_gb = 5
    base_image_id = "img-001"
    commands = [{"step": "install_py", "progress_pct": 50, "script": "echo hi"}]
    apt_packages = []


def _resource_snapshot():
    return {
        "openstack.service_project": {"id": "service-project", "name": "service"},
        "base_image": {"id": "img-001", "name": "Ubuntu"},
        "builder.flavor": {"id": "flv-001", "name": "builder"},
        "builder.network": {"id": "net-001", "name": "builder-net"},
        "manila": {
            "share_proto": "NFS",
            "share_type": "nfs-type",
            "share_network_id": "sn-001",
            "share_size_gb": 5,
        },
    }


def _make_conn():
    conn = MagicMock()
    conn.compute.create_server.return_value = MagicMock(id="server-001")
    return conn


@contextmanager
def _build_context(
    *,
    console_output=_SUCCESS_LINE,
    wait_result=(False, False),
    update_db=None,
    call_order=None,
):
    """Mock the external dependencies used by a snapshot-driven build."""
    conn = _make_conn()
    update_db = update_db or AsyncMock()
    with (
        patch(
            "app.services.keystone.get_admin_connection_for_project",
            return_value=conn,
        ),
        patch("app.services.ephemeral_build.library_recipes") as recipes,
        patch("app.services.ephemeral_build.lib_svc.get_by_id", return_value=MagicMock(version="3.11")),
        patch("app.services.ephemeral_build.ephemeral_mount") as mounts,
        patch("app.services.ephemeral_build.neutron") as neutron,
        patch("app.services.ephemeral_build.nova") as nova,
        patch("app.services.ephemeral_build.manila") as manila,
        patch("app.services.ephemeral_build.render_user_data", return_value="#cloud-config\n"),
        patch("app.services.ephemeral_build._update_db", new=update_db),
        patch(
            "app.services.ephemeral_build._wait_for_shutoff",
            new=AsyncMock(return_value=wait_result),
        ),
        patch("app.services.ephemeral_build.uuid.uuid4", return_value=MagicMock(hex=_TOKEN)),
    ):
        recipes.get_recipe = AsyncMock(return_value=_FakeRecipe())
        mounts.create_builder_share = AsyncMock(return_value="share-001")
        neutron.create_port = MagicMock(
            side_effect=(
                lambda *args, **kwargs: (
                    (call_order.append("create_port") if call_order is not None else None)
                    or {"id": "port-001", "fixed_ip": "10.0.0.5"}
                )
            )
        )
        neutron.delete_port = MagicMock()
        manila.ensure_nfs_access_rule = MagicMock(
            side_effect=(
                lambda *args, **kwargs: (
                    (call_order.append("ensure_nfs_access_rule") if call_order is not None else None)
                    or {"access_id": "rule-001"}
                )
            )
        )
        manila.get_export_locations = MagicMock(return_value=["10.0.0.1:/path"])
        manila.revoke_access_rule = MagicMock()
        manila.update_share_metadata = MagicMock()
        manila.set_share_public = MagicMock()
        nova.get_console_output = MagicMock(return_value=console_output)
        yield conn, neutron


@pytest.mark.asyncio
async def test_run_ephemeral_build_success_calls_delete_server():
    """A successful build deletes the transient server."""
    from app.services.ephemeral_build import run_ephemeral_build

    with _build_context() as (conn, _):
        await run_ephemeral_build("python311", 1, resource_snapshot=_resource_snapshot())

    conn.compute.delete_server.assert_called_once_with("server-001")


@pytest.mark.asyncio
async def test_run_ephemeral_build_success_calls_delete_port():
    """A successful build deletes the transient Neutron port."""
    from app.services.ephemeral_build import run_ephemeral_build

    with _build_context() as (_, neutron):
        await run_ephemeral_build("python311", 1, resource_snapshot=_resource_snapshot())

    neutron.delete_port.assert_called_once()


@pytest.mark.asyncio
async def test_run_ephemeral_build_failure_sentinel_marks_error():
    """A FAILURE sentinel persists an error and still cleans up the port."""
    from app.services.ephemeral_build import run_ephemeral_build

    update_calls = []

    async def capture_update(build_id, **kwargs):
        update_calls.append(kwargs)

    with _build_context(console_output=_FAILURE_LINE, update_db=capture_update) as (_, neutron):
        await run_ephemeral_build("python311", 1, resource_snapshot=_resource_snapshot())

    assert any(call.get("status") == "error" for call in update_calls)
    neutron.delete_port.assert_called_once()


@pytest.mark.asyncio
async def test_run_ephemeral_build_no_sentinel_marks_indeterminate():
    """Missing a sentinel records the explicitly indeterminate outcome."""
    from app.services.ephemeral_build import run_ephemeral_build

    update_calls = []

    async def capture_update(build_id, **kwargs):
        update_calls.append(kwargs)

    with _build_context(console_output="no sentinel here at all", update_db=capture_update) as (_, neutron):
        await run_ephemeral_build("python311", 1, resource_snapshot=_resource_snapshot())

    assert any(call.get("cloud_init_status") == "indeterminate" for call in update_calls)
    neutron.delete_port.assert_called_once()


@pytest.mark.asyncio
async def test_port_created_before_access_rule():
    """The builder port exists before a Manila rule grants it access."""
    from app.services.ephemeral_build import run_ephemeral_build

    call_order = []
    with _build_context(call_order=call_order):
        await run_ephemeral_build("python311", 1, resource_snapshot=_resource_snapshot())

    assert call_order.index("create_port") < call_order.index("ensure_nfs_access_rule")
