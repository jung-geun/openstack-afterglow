from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


def _decode_write_file(user_data: str, path: str) -> str:
    doc = yaml.safe_load(user_data)
    item = next(entry for entry in doc["write_files"] if entry["path"] == path)
    return base64.b64decode(item["content"]).decode()


def _snapshot() -> dict:
    return {
        "network": {"id": "snapshot-network", "name": "network"},
        "flavor": {"id": "snapshot-flavor", "name": "flavor"},
        "openstack.service_project": {"id": "service-project", "name": "service"},
    }


@pytest.mark.asyncio
async def test_run_layer_consume_requires_complete_snapshot_before_side_effects():
    from app.services.layer_build import run_layer_consume

    with (
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock) as update,
        patch("app.services.layer_build.neutron.create_port") as create_port,
    ):
        with pytest.raises(RuntimeError, match="resource snapshot is incomplete"):
            await run_layer_consume(1, "profile", "consumer", "ignored", resource_snapshot={})

    update.assert_not_awaited()
    create_port.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer_consume_uses_artifact_and_resource_snapshots():
    from app.services.layer_build import run_layer_consume

    connection = MagicMock()
    connection.compute.create_server.return_value = MagicMock(id="server-1")
    artifact = {
        "id": 1,
        "name": "python311",
        "share_id": "artifact-share",
        "sqsh_filename": "python311-latest.sqsh",
        "ubuntu_base": "ubuntu-20.04",
        "base_image_id": "artifact-image",
    }
    with (
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.services.layer_build.neutron.create_port", return_value={"id": "port-1", "fixed_ip": "10.0.0.5"}),
        patch("app.services.layer_build.manila.ensure_nfs_access_rule", return_value={"access_id": "rule-1"}),
        patch("app.services.layer_build.manila.get_export_locations", return_value=["10.0.0.1:/share"]),
    ):
        server_id = await run_layer_consume(
            consume_db_id=1,
            profile_name="profile",
            server_name="consumer",
            flavor_id="ignored",
            resource_snapshot=_snapshot(),
            compute_conn=connection,
            share_conn=connection,
            resolved_artifacts=[artifact],
        )

    assert server_id == "server-1"
    kwargs = connection.compute.create_server.call_args.kwargs
    assert kwargs["image_id"] == "artifact-image"
    assert kwargs["flavor_id"] == "snapshot-flavor"
    assert kwargs["metadata"]["base_image_id"] == "artifact-image"


@pytest.mark.asyncio
async def test_run_layer_consume_rejects_mixed_artifact_base_images_before_port_creation():
    from app.services.layer_build import run_layer_consume

    connection = MagicMock()
    artifacts = [
        {
            "id": 1,
            "name": "one",
            "share_id": "share-1",
            "sqsh_filename": "one.sqsh",
            "ubuntu_base": "ubuntu-22.04",
            "base_image_id": "image-a",
        },
        {
            "id": 2,
            "name": "two",
            "share_id": "share-2",
            "sqsh_filename": "two.sqsh",
            "ubuntu_base": "ubuntu-22.04",
            "base_image_id": "image-b",
        },
    ]
    with (
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.services.layer_build.neutron.create_port") as create_port,
    ):
        with pytest.raises(RuntimeError, match="base image가 일치하지 않습니다"):
            await run_layer_consume(
                1,
                "profile",
                "consumer",
                "ignored",
                resource_snapshot=_snapshot(),
                compute_conn=connection,
                share_conn=connection,
                resolved_artifacts=artifacts,
            )

    create_port.assert_not_called()


def test_render_layer_consume_user_data_includes_default_and_custom_ssh_user():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer",
        [("10.0.0.10:/share", "test-python-layer-latest.sqsh")],
        ssh_public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest termius by jung:admin #note",
        ssh_username="ubuntu",
    )
    assert "users:" in user_data
    assert "  - default" in user_data
    assert "  - name: ubuntu" in user_data
    assert '      - "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest termius by jung:admin #note"' in user_data


def test_render_layer_consume_user_data_imports_github_key_for_default_user():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer", [("10.0.0.10:/share", "test-python-layer-latest.sqsh")], github_username="octocat"
    )
    assert 'ssh_import_id:\n  - "gh:octocat"' in user_data


def test_render_layer_consume_user_data_starts_activation_on_first_boot():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer", [("10.0.0.10:/share-a", "uv-latest.sqsh"), ("10.0.0.11:/share-b", "python-latest.sqsh")]
    )
    assert "systemctl enable layer-activate.service" in user_data
    assert "systemctl start layer-activate.service" in user_data


def test_render_layer_consume_user_data_mounts_fstab_paths_before_sqsh_lookup():
    from app.services.layer_build import render_layer_consume_user_data

    script = _decode_write_file(
        render_layer_consume_user_data("test-python-layer", [("10.0.0.10:/share-a", "uv-latest.sqsh")]),
        "/usr/local/bin/layer-activate.sh",
    )
    assert "_ensure_nfs_mount()" in script
    assert '_ensure_nfs_mount "$MNTPT"' in script
    assert script.index('_ensure_nfs_mount "$MNTPT"') < script.index('SQSH_NFS="${MNTPT}/images/${SQSH_FILE}"')


def test_scaffold_layer_activate_uses_usr_lowerdirs_for_usr_overlay():
    script = (Path(__file__).resolve().parents[2] / "layers/vm/layer-activate.sh").read_text()
    assert "_layer_lowerdir()" in script
    assert 'local lower="${mount_point}/usr"' in script
    assert "BASE_USR_LOWER:-/run/afterglow/base-usr" in script
    assert 'mount --bind /usr "$BASE_LOWER"' in script
    assert "lowerdir=${LOWER_DIRS}:${BASE_LOWER}" in script
