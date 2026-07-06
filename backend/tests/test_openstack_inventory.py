from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_collect_instance_data_clears_gpu_map_for_shelved_offloaded():
    from app.services.openstack_inventory import collect_instance_data

    flavor = SimpleNamespace(
        id="flavor-gpu",
        name="gpu.3090_8c_16g",
        vcpus=8,
        ram=16384,
        extra_specs={"pci_passthrough:alias": "nvidia-rtx3090:1"},
    )
    active_server = SimpleNamespace(
        id="inst-active",
        name="active-gpu",
        status="ACTIVE",
        flavor={"id": "flavor-gpu", "original_name": "gpu.3090_8c_16g"},
        addresses={},
        created_at="2026-07-01 00:00:00",
        compute_host="compute-1",
        user_id="user-1",
        project_id="project-1",
    )
    shelved_server = SimpleNamespace(
        id="inst-shelved",
        name="shelved-gpu",
        status="SHELVED_OFFLOADED",
        flavor={"id": "flavor-gpu", "original_name": "gpu.3090_8c_16g"},
        addresses={},
        created_at="2026-07-01 00:00:00",
        compute_host="compute-1",
        user_id="user-1",
        project_id="project-1",
    )

    conn = SimpleNamespace(
        compute=SimpleNamespace(
            flavors=MagicMock(return_value=[flavor]),
            servers=MagicMock(return_value=[active_server, shelved_server]),
        ),
        identity=SimpleNamespace(
            projects=MagicMock(return_value=[SimpleNamespace(id="project-1", name="project")]),
            users=MagicMock(return_value=[SimpleNamespace(id="user-1", name="user", email="user@example.com")]),
        ),
        close=MagicMock(),
    )
    settings = SimpleNamespace(
        os_auth_url="https://openstack.example/v3",
        os_username="user",
        os_password="password",
        os_project_name="service",
        os_user_domain_name="Default",
        os_project_domain_name="Default",
        ssl_verify=True,
    )

    with (
        patch("openstack.connect", return_value=conn),
        patch("app.config.get_settings", return_value=settings),
        patch(
            "app.services.gpu_inventory.build_alias_to_device_name_map",
            return_value={"nvidia-rtx3090": "RTX 3090"},
        ),
    ):
        rows = await collect_instance_data(
            email_to_page_id={"user@example.com": "user-page"},
            host_to_page_id={"compute-1": "host-page"},
            gpu_name_to_page_id={"RTX 3090": "gpu-page"},
        )

    active = next(row for row in rows if row["instance_id"] == "inst-active")
    shelved = next(row for row in rows if row["instance_id"] == "inst-shelved")

    assert active["gpu_count"] == 1
    assert active["gpu_spec_page_id"] == "gpu-page"
    assert active["hypervisor_page_id"] == "host-page"

    assert shelved["gpu_count"] == 0
    assert shelved["gpu_spec_page_id"] == ""
    assert shelved["hypervisor_page_id"] == ""
    assert shelved["status"] == "SHELVED_OFFLOADED"
    assert shelved["gpu_name"] == "RTX 3090"
