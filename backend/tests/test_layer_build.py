"""layer_build orchestration regression tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.layer_build import (
    _CONSOLE_EXCERPT_CHARS,
    LAYER_BUILD_IMAGE_PACKAGES,
    LAYER_CONSUME_IMAGE_PACKAGES,
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


@pytest.mark.asyncio
async def test_run_layer_build_rejects_invalid_recipe_before_openstack_allocation():
    """Invalid recipes record an error before any OpenStack connection is opened."""
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.keystone.get_admin_connection_for_project") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
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
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert error_updates
    assert "kind='python'" in error_updates[-1]["error_message"]
    assert "pip_packages" in error_updates[-1]["error_message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {
                "kind": "python",
                "python_version": "3.11",
                "pip_packages": [],
                "pip_index_url": "https://download.pytorch.org/whl/cpu",
                "parent_artifact_id": 7,
            },
            "pip source",
        ),
        (
            {
                "kind": "system",
                "python_version": None,
                "pip_packages": [],
                "apt_packages": [],
            },
            "apt_packages",
        ),
    ],
)
async def test_run_layer_build_rejects_invalid_contract_before_openstack_allocation(kwargs, expected):
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.keystone.get_admin_connection_for_project") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
        await run_layer_build(build_db_id=124, layer_name="invalid", **kwargs)

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert expected in error_updates[-1]["error_message"]


@pytest.mark.asyncio
async def test_run_layer_build_requires_complete_snapshot_before_openstack_allocation():
    with (
        patch("app.services.layer_build._update_build_db", new_callable=AsyncMock) as mock_update,
        patch("app.services.keystone.get_admin_connection_for_project") as mock_get_conn,
        patch("app.services.layer_build.neutron.create_port") as mock_create_port,
    ):
        await run_layer_build(
            build_db_id=125,
            layer_name="uv",
            kind="uv",
            python_version=None,
            pip_packages=[],
            resource_snapshot={"base_image": {"id": "image-1"}},
        )

    mock_get_conn.assert_not_called()
    mock_create_port.assert_not_called()
    error_updates = [call.kwargs for call in mock_update.await_args_list if call.kwargs.get("status") == "error"]
    assert "resource snapshot is incomplete" in error_updates[-1]["error_message"]
