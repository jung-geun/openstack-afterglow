"""layer_build orchestration regression tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.layer_build import (
    _CONSOLE_EXCERPT_CHARS,
    LAYER_BUILD_IMAGE_PACKAGES,
    LAYER_CONSUME_IMAGE_PACKAGES,
    _builder_flavor_id_for_kind,
    _layer_image_id_for_ubuntu_base,
    render_layer_consume_user_data,
    run_layer_build,
)


def test_layer_build_persists_large_console_excerpt():
    assert _CONSOLE_EXCERPT_CHARS >= 12000


def test_layer_preinstall_packages_match_cloud_init_fallbacks():
    consume_user_data = render_layer_consume_user_data(
        "default",
        [("10.0.0.1:/layers/python", "python311-latest.sqsh")],
    )

    assert set(LAYER_BUILD_IMAGE_PACKAGES) == {"curl", "nfs-common", "squashfs-tools"}
    assert set(LAYER_CONSUME_IMAGE_PACKAGES) == {"nfs-common", "squashfs-tools"}
    for package in LAYER_CONSUME_IMAGE_PACKAGES:
        assert f"  - {package}" in consume_user_data
    preinstall = (
        Path(__file__).resolve().parents[2] / "layers/cloud-init/layer-image-preinstall.cloud-config.yaml"
    ).read_text()
    for package in [*LAYER_BUILD_IMAGE_PACKAGES, "ceph-common", "ca-certificates"]:
        assert f"  - {package}" in preinstall


def test_builder_flavor_id_for_kind_uses_gpu_flavor_only_for_nvidia():
    settings = MagicMock(builder_flavor_id="cpu.4c_8g")

    assert _builder_flavor_id_for_kind("nvidia", settings) == "fe5a5a4c-a568-481d-982b-469967f64808"
    assert _builder_flavor_id_for_kind("system", settings) == "cpu.4c_8g"
    assert _builder_flavor_id_for_kind("python", settings) == "cpu.4c_8g"
    assert _builder_flavor_id_for_kind("pip", settings) == "cpu.4c_8g"


def test_layer_image_id_for_ubuntu_base_uses_configured_images_and_legacy_24_fallback():
    settings = MagicMock(
        builder_ubuntu_18_04_image_id="img-18",
        builder_ubuntu_20_04_image_id="img-20",
        builder_ubuntu_22_04_image_id="img-22",
        builder_ubuntu_24_04_image_id="",
        builder_image_id="legacy-builder",
        server_image_id="legacy-server",
    )

    assert _layer_image_id_for_ubuntu_base(settings, "ubuntu-18.04") == "img-18"
    assert _layer_image_id_for_ubuntu_base(settings, "ubuntu-20.04") == "img-20"
    assert _layer_image_id_for_ubuntu_base(settings, "ubuntu-22.04") == "img-22"
    assert _layer_image_id_for_ubuntu_base(settings, "ubuntu-24.04") == "legacy-builder"


def test_layer_image_id_for_ubuntu_base_requires_non_default_config():
    settings = MagicMock(
        builder_ubuntu_18_04_image_id="",
        builder_ubuntu_20_04_image_id="",
        builder_ubuntu_22_04_image_id="",
        builder_ubuntu_24_04_image_id="",
        builder_image_id="legacy-builder",
        server_image_id="legacy-server",
    )

    with pytest.raises(RuntimeError, match="ubuntu-20.04"):
        _layer_image_id_for_ubuntu_base(settings, "ubuntu-20.04")


@pytest.mark.asyncio
async def test_run_layer_build_rejects_unconfigured_non_default_ubuntu_before_openstack_allocation():
    settings = MagicMock(
        builder_ubuntu_18_04_image_id="",
        builder_ubuntu_20_04_image_id="",
        builder_ubuntu_22_04_image_id="",
        builder_ubuntu_24_04_image_id="",
        builder_image_id="legacy-builder",
        server_image_id="legacy-server",
        builder_flavor_id="cpu.4c_8g",
        builder_network_id="net-1",
        default_network_id="",
    )
    with (
        patch("app.services.layer_build.get_settings", return_value=settings),
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.layer_build.get_service_project_connection") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
        patch("app.services.layer_build.manila.create_file_storage") as mock_create_share,
    ):
        await run_layer_build(
            build_db_id=127,
            layer_name="uv",
            kind="uv",
            python_version=None,
            pip_packages=[],
            ubuntu_base="ubuntu-20.04",
        )

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    mock_create_share.assert_not_called()
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert error_updates
    assert "ubuntu-20.04" in error_updates[-1]["error_message"]


@pytest.mark.asyncio
async def test_run_layer_build_invalid_python_with_packages_fails_before_openstack_allocation():
    """Invalid Python+pip combo records build error without allocating OpenStack resources."""
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.layer_build.get_service_project_connection") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
        patch("app.services.layer_build.manila.create_file_storage") as mock_create_share,
        patch("app.services.layer_build.manila.ensure_nfs_access_rule") as mock_ensure_rule,
        patch("app.services.layer_build._ensure_ephemeral_keypair", new_callable=AsyncMock) as mock_keypair,
    ):
        mock_get_conn.return_value = MagicMock()

        await run_layer_build(
            build_db_id=123,
            layer_name="bad-python",
            kind="python",
            python_version="3.11",
            pip_packages=["numpy==1.26.4"],
            parent_artifact_id=7,
        )

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    mock_create_share.assert_not_called()
    mock_ensure_rule.assert_not_called()
    mock_keypair.assert_not_awaited()

    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert error_updates, "expected run_layer_build to mark the build row as error"
    error_update = error_updates[-1]
    assert error_update["cloud_init_status"] == "failure"
    assert error_update["progress_step"] == "빌드 실패"
    assert error_update["completed"] is True
    assert "kind='python'" in error_update["error_message"]
    assert "pip_packages" in error_update["error_message"]


@pytest.mark.asyncio
async def test_run_layer_build_rejects_python_index_url_before_openstack_allocation():
    """Pip source options are pip-layer only and fail before OpenStack allocation."""
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.layer_build.get_service_project_connection") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
        mock_get_conn.return_value = MagicMock()

        await run_layer_build(
            build_db_id=124,
            layer_name="bad-python",
            kind="python",
            python_version="3.11",
            pip_packages=[],
            pip_index_url="https://download.pytorch.org/whl/cpu",
            parent_artifact_id=7,
        )

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert error_updates, "expected run_layer_build to mark the build row as error"
    assert "pip source" in error_updates[-1]["error_message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "python_version", "pip_packages"),
    [
        ("python", "3.11", []),
        ("pip", None, ["numpy==1.26.4"]),
    ],
)
async def test_run_layer_build_rejects_nvidia_branch_for_python_stacks_before_openstack_allocation(
    kind,
    python_version,
    pip_packages,
):
    """NVIDIA driver branch is template-only and fails before OpenStack allocation for Python stacks."""
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.layer_build.get_service_project_connection") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
        mock_get_conn.return_value = MagicMock()

        await run_layer_build(
            build_db_id=126,
            layer_name=f"bad-{kind}",
            kind=kind,
            python_version=python_version,
            pip_packages=pip_packages,
            parent_artifact_id=7,
            nvidia_driver_branch="580",
        )

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert error_updates, "expected run_layer_build to mark the build row as error"
    assert "nvidia_driver_branch" in error_updates[-1]["error_message"]


@pytest.mark.asyncio
async def test_run_layer_build_rejects_empty_system_apt_before_openstack_allocation():
    """System layers require apt packages and fail before OpenStack allocation."""
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.layer_build.get_service_project_connection") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
        patch("app.services.layer_build.manila.create_file_storage") as mock_create_share,
        patch("app.services.layer_build.manila.ensure_nfs_access_rule") as mock_ensure_rule,
        patch("app.services.layer_build._ensure_ephemeral_keypair", new_callable=AsyncMock) as mock_keypair,
    ):
        mock_get_conn.return_value = MagicMock()

        await run_layer_build(
            build_db_id=125,
            layer_name="sys-tools",
            kind="system",
            python_version=None,
            pip_packages=[],
            apt_packages=[],
        )

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    mock_create_share.assert_not_called()
    mock_ensure_rule.assert_not_called()
    mock_keypair.assert_not_awaited()
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert error_updates, "expected run_layer_build to mark the build row as error"
    assert "kind='system'" in error_updates[-1]["error_message"]
    assert "apt_packages" in error_updates[-1]["error_message"]
