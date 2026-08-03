from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mcp_control_plane.network import (
    McpNetworkError,
    get_project_network,
    get_project_subnet,
    list_project_networks,
    list_project_subnets,
    preview_project_network_delete,
    preview_project_subnet_delete,
    request_project_network_delete,
    request_project_subnet_delete,
)


@pytest.mark.asyncio
async def test_network_list_uses_separate_owned_and_shared_visibility_queries():
    calls: list[dict[str, object]] = []

    class Network:
        def networks(self, **kwargs):
            calls.append(kwargs)
            if "project_id" in kwargs:
                return [
                    SimpleNamespace(
                        id="network-a",
                        name="private-a",
                        status="ACTIVE",
                        project_id="project-a",
                        is_shared=False,
                        is_router_external=False,
                        provider_physical_network="private",
                    )
                ]
            return [
                SimpleNamespace(
                    id="network-public",
                    name="public",
                    status="ACTIVE",
                    project_id="provider-project",
                    is_shared=True,
                    is_router_external=True,
                    provider_segmentation_id="secret",
                )
            ]

    result = await list_project_networks(SimpleNamespace(network=Network()), project_id="project-a", limit=50)

    assert calls == [{"project_id": "project-a"}, {"is_shared": True}, {"is_router_external": True}]
    assert result == [
        {
            "id": "network-a",
            "name": "private-a",
            "status": "ACTIVE",
            "is_shared": False,
            "is_external": False,
            "visibility": "owned",
        },
        {
            "id": "network-public",
            "name": "public",
            "status": "ACTIVE",
            "is_shared": True,
            "is_external": True,
            "visibility": "shared",
        },
    ]


@pytest.mark.asyncio
async def test_network_get_rejects_foreign_private_networks():
    class Network:
        def get_network(self, _network_id):
            return SimpleNamespace(
                id="network-b", name="foreign", status="ACTIVE", project_id="project-b", is_shared=False
            )

    with pytest.raises(McpNetworkError, match="ownership"):
        await get_project_network(SimpleNamespace(network=Network()), project_id="project-a", network_id="network-b")


@pytest.mark.asyncio
async def test_subnet_list_uses_project_filter_and_proves_visible_parent():
    calls: list[tuple[str, object]] = []

    class Network:
        def subnets(self, **kwargs):
            calls.append(("subnets", kwargs))
            return [
                SimpleNamespace(
                    id="subnet-a",
                    name="private-subnet",
                    network_id="network-a",
                    cidr="10.0.0.0/24",
                    ip_version=4,
                    gateway_ip="10.0.0.1",
                    project_id="project-a",
                    allocation_pools=[{"start": "10.0.0.10", "end": "10.0.0.200"}],
                )
            ]

        def get_network(self, network_id):
            calls.append(("get_network", network_id))
            return SimpleNamespace(
                id=network_id,
                name="private-a",
                status="ACTIVE",
                project_id="project-a",
                is_shared=False,
                is_router_external=False,
            )

    result = await list_project_subnets(SimpleNamespace(network=Network()), project_id="project-a", limit=50)

    assert calls == [
        ("subnets", {"project_id": "project-a"}),
        ("get_network", "network-a"),
    ]
    assert result == [
        {
            "id": "subnet-a",
            "name": "private-subnet",
            "network_id": "network-a",
            "cidr": "10.0.0.0/24",
            "ip_version": 4,
            "gateway_ip": "10.0.0.1",
        }
    ]


@pytest.mark.asyncio
async def test_subnet_get_rejects_foreign_parent_network():
    class Network:
        def get_subnet(self, _subnet_id):
            return SimpleNamespace(
                id="subnet-a",
                name="private-subnet",
                network_id="network-a",
                cidr="10.0.0.0/24",
                ip_version=4,
                gateway_ip="10.0.0.1",
                project_id="project-a",
            )

        def get_network(self, network_id):
            return SimpleNamespace(
                id=network_id,
                name="private-b",
                status="ACTIVE",
                project_id="project-b",
                is_shared=False,
                is_router_external=False,
            )

    with pytest.raises(McpNetworkError, match="ownership"):
        await get_project_subnet(SimpleNamespace(network=Network()), project_id="project-a", subnet_id="subnet-a")


@pytest.mark.asyncio
async def test_network_delete_revalidates_owned_network_without_force():
    calls: list[tuple[str, object]] = []

    class Network:
        def get_network(self, network_id):
            calls.append(("get_network", network_id))
            return SimpleNamespace(
                id=network_id,
                name="private-a",
                status="ACTIVE",
                project_id="project-a",
                is_shared=False,
                is_router_external=False,
            )

        def delete_network(self, network_id, **kwargs):
            calls.append(("delete_network", (network_id, kwargs)))

    conn = SimpleNamespace(network=Network())
    preview = await preview_project_network_delete(conn, project_id="project-a", network_id="network-a")
    result = await request_project_network_delete(conn, project_id="project-a", network_id="network-a")

    assert preview["requested_action"] == "delete"
    assert result["requested_action"] == "delete"
    assert calls == [
        ("get_network", "network-a"),
        ("get_network", "network-a"),
        ("delete_network", ("network-a", {"ignore_missing": False})),
    ]


@pytest.mark.asyncio
async def test_network_delete_rejects_shared_or_foreign_targets_before_provider_call():
    calls: list[str] = []

    class Network:
        def get_network(self, network_id):
            return SimpleNamespace(
                id=network_id,
                name="public",
                status="ACTIVE",
                project_id="project-a",
                is_shared=True,
                is_router_external=True,
            )

        def delete_network(self, network_id, **_kwargs):
            calls.append(network_id)

    with pytest.raises(McpNetworkError, match="shared"):
        await request_project_network_delete(
            SimpleNamespace(network=Network()),
            project_id="project-a",
            network_id="network-public",
        )

    assert calls == []


@pytest.mark.asyncio
async def test_subnet_delete_revalidates_owned_non_shared_parent_without_force():
    calls: list[tuple[str, object]] = []

    class Network:
        def get_subnet(self, subnet_id):
            calls.append(("get_subnet", subnet_id))
            return SimpleNamespace(
                id=subnet_id,
                name="private-subnet",
                network_id="network-a",
                cidr="10.0.0.0/24",
                ip_version=4,
                gateway_ip="10.0.0.1",
                project_id="project-a",
            )

        def get_network(self, network_id):
            calls.append(("get_network", network_id))
            return SimpleNamespace(
                id=network_id,
                name="private-a",
                status="ACTIVE",
                project_id="project-a",
                is_shared=False,
                is_router_external=False,
            )

        def delete_subnet(self, subnet_id, **kwargs):
            calls.append(("delete_subnet", (subnet_id, kwargs)))

    conn = SimpleNamespace(network=Network())
    preview = await preview_project_subnet_delete(conn, project_id="project-a", subnet_id="subnet-a")
    result = await request_project_subnet_delete(conn, project_id="project-a", subnet_id="subnet-a")

    assert preview["requested_action"] == "delete"
    assert result["requested_action"] == "delete"
    assert calls == [
        ("get_subnet", "subnet-a"),
        ("get_network", "network-a"),
        ("get_network", "network-a"),
        ("get_subnet", "subnet-a"),
        ("get_network", "network-a"),
        ("get_network", "network-a"),
        ("delete_subnet", ("subnet-a", {"ignore_missing": False})),
    ]


@pytest.mark.asyncio
async def test_subnet_delete_rejects_shared_parent_before_provider_call():
    calls: list[str] = []

    class Network:
        def get_subnet(self, subnet_id):
            return SimpleNamespace(
                id=subnet_id,
                name="shared-subnet",
                network_id="network-shared",
                cidr="10.0.0.0/24",
                ip_version=4,
                gateway_ip="10.0.0.1",
                project_id="project-a",
            )

        def get_network(self, network_id):
            return SimpleNamespace(
                id=network_id,
                name="shared",
                status="ACTIVE",
                project_id="project-a",
                is_shared=True,
                is_router_external=False,
            )

        def delete_subnet(self, subnet_id, **_kwargs):
            calls.append(subnet_id)

    with pytest.raises(McpNetworkError, match="shared"):
        await request_project_subnet_delete(
            SimpleNamespace(network=Network()),
            project_id="project-a",
            subnet_id="subnet-a",
        )

    assert calls == []
