from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


class _ScalarResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Session:
    def __init__(self, rows):
        self._rows = list(rows)

    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(self._rows.pop(0))


class _AssertingLimitSession(_Session):
    def __init__(self, rows):
        super().__init__(rows)
        self.saw_limit = False

    async def execute(self, stmt, *_args, **_kwargs):
        self.saw_limit = getattr(stmt, "_limit_clause", None) is not None
        return await super().execute(stmt)


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_session_factory(*sessions):
    contexts = iter(_SessionContext(session) for session in sessions)

    def _factory():
        return next(contexts)

    return _factory


def _decode_write_file(user_data: str, path: str) -> str:
    doc = yaml.safe_load(user_data)
    item = next(entry for entry in doc["write_files"] if entry["path"] == path)
    return base64.b64decode(item["content"]).decode()


@pytest.mark.asyncio
async def test_run_layer_consume_unknown_flavor_stops_before_side_effects():
    settings = MagicMock(
        server_image_id="img-1",
        builder_image_id="",
        default_network_id="net-1",
        builder_network_id="",
    )
    conn = MagicMock()
    conn.compute.find_flavor.return_value = None

    profile_row = MagicMock(layers=["test-python-layer"])
    artifact_row = MagicMock(
        share_id="share-1",
        sqsh_filename="test-python-layer-latest.sqsh",
        ubuntu_base="ubuntu-24.04",
        base_image_id="img-24",
    )
    session_factory = _make_session_factory(_Session([profile_row]), _Session([artifact_row]))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection", return_value=conn),
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock) as mock_update,
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
        patch("app.services.layer_build.manila.ensure_nfs_access_rule") as mock_ensure_rule,
        patch("app.services.layer_build.manila.get_export_locations") as mock_get_exports,
    ):
        from app.services.layer_build import run_layer_consume

        with pytest.raises(RuntimeError, match="플레이버를 찾을 수 없습니다: 'cpu.4c_8g'"):
            await run_layer_consume(
                consume_db_id=7,
                profile_name="test-python-layer",
                server_name="consumer-01",
                flavor_id="cpu.4c_8g",
                image_id=None,
                network_id=None,
            )

    conn.compute.find_flavor.assert_called_once_with("cpu.4c_8g")
    conn.compute.create_server.assert_not_called()
    mock_create_port.assert_not_called()
    mock_ensure_rule.assert_not_called()
    mock_get_exports.assert_not_called()
    assert mock_update.await_args_list[0].kwargs == {"status": "creating"}
    assert mock_update.await_args_list[-1].kwargs["status"] == "error"


@pytest.mark.asyncio
async def test_run_layer_consume_uses_profile_ubuntu_image_when_image_id_empty():
    settings = MagicMock(
        server_image_id="legacy-server",
        builder_image_id="legacy-builder",
        builder_ubuntu_18_04_image_id="img-18",
        builder_ubuntu_20_04_image_id="img-20",
        builder_ubuntu_22_04_image_id="img-22",
        builder_ubuntu_24_04_image_id="img-24",
        default_network_id="net-1",
        builder_network_id="",
    )
    conn = MagicMock()
    conn.compute.find_flavor.return_value = MagicMock(id="flavor-1")
    conn.compute.create_server.return_value = MagicMock(id="server-1")

    profile_row = MagicMock(layers=["python311"])
    artifact_row = MagicMock(
        share_id="share-1", sqsh_filename="python311-latest.sqsh", ubuntu_base="ubuntu-20.04", base_image_id="img-20"
    )
    session_factory = _make_session_factory(_Session([profile_row]), _Session([artifact_row]))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection", return_value=conn),
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port", return_value={"id": "port-1", "fixed_ip": "10.0.0.5"}),
        patch("app.services.layer_build.manila.ensure_nfs_access_rule", return_value={"access_id": "rule-1"}),
        patch("app.services.layer_build.manila.get_export_locations", return_value=["10.0.0.1:/share"]),
    ):
        from app.services.layer_build import run_layer_consume

        server_id = await run_layer_consume(
            consume_db_id=9,
            profile_name="default",
            server_name="consumer-01",
            flavor_id="cpu.4c_8g",
            image_id=None,
            network_id=None,
        )

    assert server_id == "server-1"
    assert conn.compute.create_server.call_args.kwargs["image_id"] == "img-20"
    assert conn.compute.create_server.call_args.kwargs["metadata"]["ubuntu_base"] == "ubuntu-20.04"
    assert conn.compute.create_server.call_args.kwargs["metadata"]["base_image_id"] == "img-20"


@pytest.mark.asyncio
async def test_run_layer_consume_renders_profile_mounts_child_first():
    settings = MagicMock(
        server_image_id="legacy-server",
        builder_image_id="legacy-builder",
        builder_ubuntu_18_04_image_id="",
        builder_ubuntu_20_04_image_id="",
        builder_ubuntu_22_04_image_id="",
        builder_ubuntu_24_04_image_id="img-24",
        default_network_id="net-1",
        builder_network_id="",
    )
    conn = MagicMock()
    conn.compute.find_flavor.return_value = MagicMock(id="flavor-1")
    conn.compute.create_server.return_value = MagicMock(id="server-1")

    profile_row = MagicMock(layers=["uv", "python311", "torch"])
    artifact_rows = [
        MagicMock(
            share_id="share-uv", sqsh_filename="uv-latest.sqsh", ubuntu_base="ubuntu-24.04", base_image_id="img-24"
        ),
        MagicMock(
            share_id="share-python",
            sqsh_filename="python311-latest.sqsh",
            ubuntu_base="ubuntu-24.04",
            base_image_id="img-24",
        ),
        MagicMock(
            share_id="share-torch",
            sqsh_filename="torch-latest.sqsh",
            ubuntu_base="ubuntu-24.04",
            base_image_id="img-24",
        ),
    ]
    session_factory = _make_session_factory(_Session([profile_row]), _Session(artifact_rows))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection", return_value=conn),
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port", return_value={"id": "port-1", "fixed_ip": "10.0.0.5"}),
        patch("app.services.layer_build.manila.ensure_nfs_access_rule", return_value={"access_id": "rule-1"}),
        patch(
            "app.services.layer_build.manila.get_export_locations",
            side_effect=[
                ["10.0.0.1:/share-uv"],
                ["10.0.0.1:/share-python"],
                ["10.0.0.1:/share-torch"],
            ],
        ),
    ):
        from app.services.layer_build import run_layer_consume

        await run_layer_consume(
            consume_db_id=10,
            profile_name="default",
            server_name="consumer-01",
            flavor_id="cpu.4c_8g",
            image_id=None,
            network_id=None,
        )

    cloud_config = base64.b64decode(conn.compute.create_server.call_args.kwargs["user_data"]).decode()
    profile_conf = _decode_write_file(cloud_config, "/etc/afterglow/layers/default.conf")

    assert profile_conf.splitlines() == [
        "/mnt/nfs-layers/0|torch-latest.sqsh",
        "/mnt/nfs-layers/1|python311-latest.sqsh",
        "/mnt/nfs-layers/2|uv-latest.sqsh",
    ]


@pytest.mark.asyncio
async def test_run_layer_consume_rejects_mixed_ubuntu_bases_before_side_effects():
    settings = MagicMock(
        server_image_id="legacy-server",
        builder_image_id="legacy-builder",
        default_network_id="net-1",
        builder_network_id="",
    )
    profile_row = MagicMock(layers=["uv", "python311"])
    uv_row = MagicMock(
        share_id="share-uv", sqsh_filename="uv-latest.sqsh", ubuntu_base="ubuntu-20.04", base_image_id="img-20"
    )
    python_row = MagicMock(
        share_id="share-py", sqsh_filename="python311-latest.sqsh", ubuntu_base="ubuntu-22.04", base_image_id="img-22"
    )
    session_factory = _make_session_factory(_Session([profile_row]), _Session([uv_row, python_row]))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection") as mock_conn_factory,
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock) as mock_update,
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
        patch("app.services.layer_build.manila.ensure_nfs_access_rule") as mock_ensure_rule,
    ):
        from app.services.layer_build import run_layer_consume

        with pytest.raises(RuntimeError, match="Ubuntu base가 일치하지 않습니다"):
            await run_layer_consume(
                consume_db_id=10,
                profile_name="default",
                server_name="consumer-01",
                flavor_id="cpu.4c_8g",
                image_id=None,
                network_id=None,
            )

    mock_conn_factory.assert_not_called()
    mock_create_port.assert_not_called()
    mock_ensure_rule.assert_not_called()
    assert mock_update.await_args_list[-1].kwargs["status"] == "error"


@pytest.mark.asyncio
async def test_run_layer_consume_rejects_mixed_base_image_ids_before_side_effects():
    settings = MagicMock(default_network_id="net-1", builder_network_id="")
    profile_row = MagicMock(layers=["uv", "python311"])
    uv_row = MagicMock(
        share_id="share-uv", sqsh_filename="uv-latest.sqsh", ubuntu_base="ubuntu-22.04", base_image_id="img-a"
    )
    python_row = MagicMock(
        share_id="share-py", sqsh_filename="python311-latest.sqsh", ubuntu_base="ubuntu-22.04", base_image_id="img-b"
    )
    session_factory = _make_session_factory(_Session([profile_row]), _Session([uv_row, python_row]))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection") as mock_conn_factory,
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
        from app.services.layer_build import run_layer_consume

        with pytest.raises(RuntimeError, match="base image가 일치하지 않습니다"):
            await run_layer_consume(10, "default", "consumer-01", "cpu.4c_8g")

    mock_conn_factory.assert_not_called()
    mock_create_port.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer_consume_rejects_explicit_mismatched_image_before_side_effects():
    settings = MagicMock(default_network_id="net-1", builder_network_id="")
    profile_row = MagicMock(layers=["python311"])
    artifact_row = MagicMock(
        share_id="share-py", sqsh_filename="python311-latest.sqsh", ubuntu_base="ubuntu-22.04", base_image_id="img-22"
    )
    session_factory = _make_session_factory(_Session([profile_row]), _Session([artifact_row]))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection") as mock_conn_factory,
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
        from app.services.layer_build import run_layer_consume

        with pytest.raises(RuntimeError, match="image_id가 프로필 base image와 일치하지 않습니다"):
            await run_layer_consume(10, "default", "consumer-01", "cpu.4c_8g", image_id="other-img")

    mock_conn_factory.assert_not_called()
    mock_create_port.assert_not_called()


@pytest.mark.asyncio
async def test_run_layer_consume_requires_sealed_artifact_before_side_effects():
    settings = MagicMock(
        server_image_id="img-1",
        builder_image_id="",
        default_network_id="net-1",
        builder_network_id="",
    )
    conn = MagicMock()
    conn.compute.find_flavor.return_value = MagicMock(id="flavor-1")

    profile_row = MagicMock(layers=["python311"])
    session_factory = _make_session_factory(_Session([profile_row]), _Session([None]))

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection", return_value=conn),
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock) as mock_update,
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
        patch("app.services.layer_build.manila.ensure_nfs_access_rule") as mock_ensure_rule,
    ):
        from app.services.layer_build import run_layer_consume

        with pytest.raises(RuntimeError, match="봉인된 레이어 아티팩트를 찾을 수 없습니다: 'python311'"):
            await run_layer_consume(
                consume_db_id=8,
                profile_name="default",
                server_name="consumer-01",
                flavor_id="cpu.4c_8g",
                image_id=None,
                network_id=None,
            )

    mock_create_port.assert_not_called()
    mock_ensure_rule.assert_not_called()
    assert mock_update.await_args_list[0].kwargs == {"status": "creating"}
    assert mock_update.await_args_list[-1].kwargs["status"] == "error"


@pytest.mark.asyncio
async def test_run_layer_consume_limits_duplicate_sealed_artifact_lookup():
    settings = MagicMock(
        server_image_id="img-1",
        builder_image_id="",
        default_network_id="net-1",
        builder_network_id="",
    )
    conn = MagicMock()
    conn.compute.find_flavor.return_value = MagicMock(id="flavor-1")

    profile_row = MagicMock(layers=["python311"])
    artifact_row = MagicMock(
        share_id="share-latest",
        sqsh_filename="python311-latest.sqsh",
        ubuntu_base="ubuntu-24.04",
        base_image_id="img-24",
    )
    artifact_session = _AssertingLimitSession([artifact_row])
    session_factory = _make_session_factory(_Session([profile_row]), artifact_session)

    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build.get_service_project_connection", return_value=conn),
        patch("app.services.layer_build._update_consume_db", new_callable=AsyncMock),
        patch("app.database.get_session_factory", return_value=session_factory),
        patch("app.services.layer_build.neutron.create_port", side_effect=RuntimeError("stop after artifact lookup")),
    ):
        from app.services.layer_build import run_layer_consume

        with pytest.raises(RuntimeError, match="stop after artifact lookup"):
            await run_layer_consume(
                consume_db_id=9,
                profile_name="default",
                server_name="consumer-01",
                flavor_id="cpu.4c_8g",
                image_id=None,
                network_id=None,
            )

    assert artifact_session.saw_limit is True


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


def test_render_layer_consume_user_data_injects_key_to_default_user_when_username_empty():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer",
        [("10.0.0.10:/share", "test-python-layer-latest.sqsh")],
        ssh_public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest termius by jung:admin #note",
        ssh_username=None,
    )

    assert '  - "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest termius by jung:admin #note"' in user_data
    assert "users:" not in user_data


def test_render_layer_consume_user_data_imports_github_key_for_default_user():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer",
        [("10.0.0.10:/share", "test-python-layer-latest.sqsh")],
        github_username="octocat",
    )

    assert 'ssh_import_id:\n  - "gh:octocat"' in user_data


def test_render_layer_consume_user_data_starts_activation_on_first_boot():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer",
        [
            ("10.0.0.10:/share-a", "uv-latest.sqsh"),
            ("10.0.0.11:/share-b", "python-latest.sqsh"),
        ],
    )

    assert "systemctl enable layer-activate.service" in user_data
    assert "systemctl start layer-activate.service" in user_data
    assert user_data.index("systemctl enable layer-activate.service") < user_data.index(
        "systemctl start layer-activate.service"
    )


def test_render_layer_consume_user_data_mounts_fstab_paths_before_sqsh_lookup():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer",
        [
            ("10.0.0.10:/share-a", "uv-latest.sqsh"),
            ("10.0.0.11:/share-b", "python-latest.sqsh"),
        ],
    )

    script = _decode_write_file(user_data, "/usr/local/bin/layer-activate.sh")

    assert "_ensure_nfs_mount()" in script
    assert 'mount "$mntpt"' in script
    assert '_ensure_nfs_mount "$MNTPT"' in script
    assert script.index('_ensure_nfs_mount "$MNTPT"') < script.index('SQSH_NFS="${MNTPT}/images/${SQSH_FILE}"')


def test_render_layer_consume_user_data_uses_usr_lowerdirs_for_usr_overlay():
    from app.services.layer_build import render_layer_consume_user_data

    user_data = render_layer_consume_user_data(
        "test-python-layer",
        [
            ("10.0.0.10:/share-a", "uv-latest.sqsh"),
            ("10.0.0.11:/share-b", "python-latest.sqsh"),
        ],
    )

    script = _decode_write_file(user_data, "/usr/local/bin/layer-activate.sh")

    assert "_layer_lowerdir()" in script
    assert 'local lower="${mount_point}/usr"' in script
    assert "BASE_USR_LOWER:-/run/afterglow/base-usr" in script
    assert 'mount --bind /usr "$BASE_LOWER"' in script
    assert "lowerdir=${LOWER_DIRS}:${BASE_LOWER}" in script
    assert 'LOWER_DIRS="${LOWER_DIRS:+${LOWER_DIRS}:}${MOUNT_POINT}"' not in script
    branch_idx = script.index('if mountpoint -q "$MOUNT_POINT"')
    lower_idx = script.index('LAYER_LOWER="$(_layer_lowerdir "$MOUNT_POINT")"', branch_idx)
    continue_idx = script.index("continue", lower_idx)
    assert lower_idx < continue_idx


def test_scaffold_layer_activate_uses_usr_lowerdirs_for_usr_overlay():
    script = (Path(__file__).resolve().parents[2] / "layers/vm/layer-activate.sh").read_text()

    assert "_layer_lowerdir()" in script
    assert 'local lower="${mount_point}/usr"' in script
    assert "BASE_USR_LOWER:-/run/afterglow/base-usr" in script
    assert 'mount --bind /usr "$BASE_LOWER"' in script
    assert "lowerdir=${LOWER_DIRS}:${BASE_LOWER}" in script
    assert 'LOWER_DIRS="${LOWER_DIRS:+${LOWER_DIRS}:}${MOUNT_POINT}"' not in script
