"""Global discovered-resource policy registry and OpenStack validation.

Policies store stable resource IDs.  Display names are snapshots only; every
write revalidates the ID against the configured administrative OpenStack
connection so deleted, wrong-kind, or non-external selections cannot persist.
"""

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from app.services import glance, manila, neutron, nova


@dataclass(frozen=True)
class PolicySpec:
    key: str
    resource_kind: str
    title: str
    external_only: bool = False
    shared_only: bool = False
    execution_scope: str = "tenant"


_POLICY_SPECS = (
    PolicySpec("k3s.server_image", "image", "K3s server image"),
    PolicySpec("k3s.fcos_image", "image", "K3s Fedora CoreOS image"),
    PolicySpec("k3s.server_flavor", "flavor", "K3s server flavor"),
    PolicySpec("k3s.default_agent_flavor", "flavor", "K3s default agent flavor"),
    PolicySpec("k3s.occm_floating_network", "network", "K3s OCCM floating network", external_only=True),
    PolicySpec("k3s.api_lb_vip_network", "network", "K3s API load-balancer network", shared_only=True),
    PolicySpec("k3s.api_lb_floating_network", "network", "K3s API load-balancer floating network", external_only=True),
    PolicySpec("k3s.octavia_ingress_subnet", "subnet", "K3s Octavia ingress subnet"),
    PolicySpec(
        "k3s.octavia_ingress_floating_network", "network", "K3s Octavia ingress floating network", external_only=True
    ),
    PolicySpec("builder.image", "image", "Layer builder image", execution_scope="service"),
    PolicySpec("builder.flavor", "flavor", "Layer builder flavor", execution_scope="service"),
    PolicySpec("builder.network", "network", "Layer builder network", execution_scope="service"),
    PolicySpec(
        "builder.floating_network",
        "network",
        "Layer builder floating network",
        external_only=True,
        execution_scope="service",
    ),
    PolicySpec("nova.default_network", "network", "Default tenant network", shared_only=True),
    PolicySpec("builder.ubuntu_18_04_image", "image", "Ubuntu 18.04 layer builder image", execution_scope="service"),
    PolicySpec("builder.ubuntu_20_04_image", "image", "Ubuntu 20.04 layer builder image", execution_scope="service"),
    PolicySpec("builder.ubuntu_22_04_image", "image", "Ubuntu 22.04 layer builder image", execution_scope="service"),
    PolicySpec("builder.ubuntu_24_04_image", "image", "Ubuntu 24.04 layer builder image", execution_scope="service"),
    PolicySpec("nova.default_external_network", "network", "Default external network", external_only=True),
    PolicySpec("manila.share_network", "share_network", "Manila share network", execution_scope="service"),
    PolicySpec("waygate.provider_network", "network", "Waygate provider network", shared_only=True),
    PolicySpec("waygate.image", "image", "Waygate image"),
    PolicySpec("waygate.flavor", "flavor", "Waygate flavor"),
)
POLICY_SPECS = {spec.key: spec for spec in _POLICY_SPECS}


class ResourcePolicyValidationError(ValueError):
    """Selected resource cannot satisfy its declared global policy."""


def get_spec(key: str) -> PolicySpec:
    try:
        return POLICY_SPECS[key]
    except KeyError as exc:
        raise ResourcePolicyValidationError("unknown resource policy") from exc


def list_specs() -> list[PolicySpec]:
    return list(_POLICY_SPECS)


def _option(resource_id: object, name: object, **extra: Any) -> dict[str, Any]:
    return {"id": str(resource_id), "name": str(name or resource_id), **extra}


def _discover_sync(conn, spec: PolicySpec) -> list[dict[str, Any]]:
    if spec.resource_kind == "image":
        images = glance.list_images(conn)
        if spec.execution_scope == "tenant":
            images = [image for image in images if image.visibility in {"public", "community"}]
        return [_option(image.id, image.name, status=image.status) for image in images]
    if spec.resource_kind == "flavor":
        flavors = nova.list_flavors(conn)
        if spec.execution_scope == "tenant":
            flavors = [flavor for flavor in flavors if flavor.is_public]
        return [_option(flavor.id, flavor.name, vcpus=flavor.vcpus, ram=flavor.ram) for flavor in flavors]
    if spec.resource_kind == "network":
        options = [
            _option(
                network.id,
                network.name,
                is_external=bool(network.is_external),
                is_shared=bool(getattr(network, "is_shared", False)),
            )
            for network in neutron.list_networks(conn)
        ]
        return [
            option
            for option in options
            if (not spec.external_only or option["is_external"]) and (not spec.shared_only or option["is_shared"])
        ]
    if spec.resource_kind == "subnet":
        options = []
        for subnet in conn.network.subnets():
            parent = conn.network.get_network(subnet.network_id)
            if spec.execution_scope == "tenant" and not (
                bool(getattr(parent, "is_shared", False)) or bool(getattr(parent, "is_router_external", False))
            ):
                continue
            options.append(_option(subnet.id, subnet.name, network_id=subnet.network_id, cidr=subnet.cidr))
        return options
    if spec.resource_kind == "share_network":
        return [
            _option(item.get("id"), item.get("name")) for item in manila.list_share_networks(conn) if item.get("id")
        ]
    raise AssertionError(f"unsupported resource kind: {spec.resource_kind}")


async def discovery_connection(admin_conn, spec: PolicySpec):
    """Use the same OpenStack scope as the eventual provisioning operation."""
    if spec.execution_scope == "service":
        from app.services.keystone import get_service_project_connection

        return await asyncio.to_thread(get_service_project_connection)
    return admin_conn


async def discover_options(conn, key: str) -> list[dict[str, Any]]:
    spec = get_spec(key)
    execution_conn = await discovery_connection(conn, spec)
    owns_connection = execution_conn is not conn
    try:
        return await asyncio.to_thread(_discover_sync, execution_conn, spec)
    finally:
        if owns_connection:
            with suppress(Exception):
                await asyncio.to_thread(execution_conn.close)


def _validate_existing_sync(conn, spec: PolicySpec, resource_id: str) -> dict[str, Any]:
    """Validate one persisted ID without re-enumerating a resource catalog."""
    if spec.resource_kind == "image":
        image = conn.image.get_image(resource_id)
        if image is None or (
            spec.execution_scope == "tenant" and getattr(image, "visibility", None) not in {"public", "community"}
        ):
            raise ResourcePolicyValidationError("selected image is unavailable in the execution scope")
        return _option(image.id, image.name, status=getattr(image, "status", None))
    if spec.resource_kind == "flavor":
        flavor = conn.compute.get_flavor(resource_id)
        if flavor is None or (spec.execution_scope == "tenant" and not bool(getattr(flavor, "is_public", False))):
            raise ResourcePolicyValidationError("selected flavor is unavailable in the execution scope")
        return _option(flavor.id, flavor.name)
    if spec.resource_kind == "network":
        network = conn.network.get_network(resource_id)
        if (
            network is None
            or (spec.external_only and not bool(getattr(network, "is_router_external", False)))
            or (spec.shared_only and not bool(getattr(network, "is_shared", False)))
        ):
            raise ResourcePolicyValidationError("selected network is unavailable in the execution scope")
        return _option(network.id, network.name)
    if spec.resource_kind == "subnet":
        subnet = conn.network.get_subnet(resource_id)
        parent = conn.network.get_network(subnet.network_id) if subnet is not None else None
        if (
            subnet is None
            or parent is None
            or (
                spec.execution_scope == "tenant"
                and not (
                    bool(getattr(parent, "is_shared", False)) or bool(getattr(parent, "is_router_external", False))
                )
            )
        ):
            raise ResourcePolicyValidationError("selected subnet is unavailable in the execution scope")
        return _option(subnet.id, subnet.name)
    if spec.resource_kind == "share_network":
        share_network = manila.get_share_network(conn, resource_id)
        if not share_network or not share_network.get("id"):
            raise ResourcePolicyValidationError("selected share network is unavailable in the execution scope")
        return _option(share_network["id"], share_network.get("name"))
    raise ResourcePolicyValidationError("resource kind requires catalog validation")


async def validate_existing_selection(conn, key: str, resource_id: str) -> dict[str, Any]:
    return await asyncio.to_thread(_validate_existing_sync, conn, get_spec(key), resource_id)


async def validate_selection(conn, key: str, resource_id: str | None) -> dict[str, Any] | None:
    if resource_id is None:
        return None
    normalized = resource_id.strip()
    if not normalized:
        return None
    options = await discover_options(conn, key)
    for option in options:
        if option["id"] == normalized:
            return option
    raise ResourcePolicyValidationError("selected resource is unavailable or violates policy constraints")
