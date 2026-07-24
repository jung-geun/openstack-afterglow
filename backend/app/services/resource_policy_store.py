"""Persistence for global OpenStack resource policies."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.database import get_session_factory, is_db_available, mark_db_unhealthy
from app.models.db import ResourcePolicy
from app.services.resource_policies import (
    PolicySpec,
    ResourcePolicyValidationError,
    get_spec,
    list_specs,
    validate_existing_selection,
    validate_selection,
)

_SETTING_FIELDS = {
    "k3s.server_image": "k3s_server_image_id",
    "k3s.fcos_image": "k3s_fcos_image_id",
    "k3s.server_flavor": "k3s_server_flavor_id",
    "k3s.default_agent_flavor": "k3s_default_agent_flavor_id",
    "k3s.occm_floating_network": "k3s_occm_floating_network_id",
    "k3s.api_lb_vip_network": "k3s_api_lb_vip_network_id",
    "k3s.api_lb_floating_network": "k3s_api_lb_floating_network_id",
    "k3s.octavia_ingress_subnet": "k3s_octavia_ingress_subnet_id",
    "k3s.octavia_ingress_floating_network": "k3s_octavia_ingress_floating_network_id",
    "builder.image": "builder_image_id",
    "builder.ubuntu_18_04_image": "builder_ubuntu_18_04_image_id",
    "builder.ubuntu_20_04_image": "builder_ubuntu_20_04_image_id",
    "builder.ubuntu_22_04_image": "builder_ubuntu_22_04_image_id",
    "builder.ubuntu_24_04_image": "builder_ubuntu_24_04_image_id",
    "builder.flavor": "builder_flavor_id",
    "builder.network": "builder_network_id",
    "builder.floating_network": "builder_floating_network_id",
    "nova.default_network": "default_network_id",
    "nova.default_external_network": "default_network_external_id",
    "manila.share_network": "os_manila_share_network_id",
    "waygate.provider_network": "waygate_provider_network_id",
    "waygate.image": "waygate_image_id",
    "waygate.flavor": "waygate_flavor_id",
}


class ResourcePolicyStorageUnavailable(RuntimeError):
    pass


def _require_db():
    if not is_db_available() or (factory := get_session_factory()) is None:
        raise ResourcePolicyStorageUnavailable("resource policy storage is unavailable")
    return factory


def _public(row: ResourcePolicy | None, spec: PolicySpec) -> dict:
    return {
        "key": spec.key,
        "resource_kind": spec.resource_kind,
        "title": spec.title,
        "external_only": spec.external_only,
        "resource_id": row.resource_id if row else None,
        "resource_name": row.resource_name if row else None,
        "constraints": row.constraints if row else None,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


async def list_policies() -> list[dict]:
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (await session.execute(select(ResourcePolicy))).scalars().all()
            by_key = {row.policy_key: row for row in rows}
            return [_public(by_key.get(spec.key), spec) for spec in list_specs()]
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ResourcePolicyStorageUnavailable("resource policy storage failed") from exc


async def refresh_runtime_settings() -> None:
    """Make database policy IDs the sole runtime selector source."""
    from app.config import get_settings

    factory = _require_db()
    try:
        async with factory() as session:
            rows = (await session.execute(select(ResourcePolicy))).scalars().all()
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ResourcePolicyStorageUnavailable("resource policy storage failed") from exc
    values = {row.policy_key: row.resource_id or "" for row in rows}
    settings = get_settings()
    for policy_key, field in _SETTING_FIELDS.items():
        setattr(settings, field, values.get(policy_key, ""))


async def set_policy(*, conn, key: str, resource_id: str | None, updated_by_user_id: str) -> dict:
    spec = get_spec(key)
    selected = await validate_selection(conn, key, resource_id)
    factory = _require_db()
    try:
        async with factory() as session, session.begin():
            row = await session.get(ResourcePolicy, spec.key, with_for_update=True)
            if row is None:
                row = ResourcePolicy(policy_key=spec.key, resource_kind=spec.resource_kind)
                session.add(row)
            row.resource_id = selected["id"] if selected else None
            row.resource_name = selected["name"] if selected else None
            row.constraints = {"external_only": spec.external_only}
            row.updated_by_user_id = updated_by_user_id
            await session.flush()
            result = _public(row, spec)
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ResourcePolicyStorageUnavailable("resource policy storage failed") from exc
    await refresh_runtime_settings()
    return result


async def resolve_policies(*, conn, keys: tuple[str, ...]) -> dict[str, str]:
    """Resolve one immutable policy snapshot without catalog scans per key."""
    specs: dict[str, PolicySpec] = {key: get_spec(key) for key in keys}
    factory = _require_db()
    try:
        async with factory() as session:
            rows = (await session.execute(select(ResourcePolicy).where(ResourcePolicy.policy_key.in_(specs)))).scalars()
            resource_ids = {row.policy_key: row.resource_id for row in rows}
    except OperationalError as exc:
        mark_db_unhealthy()
        raise ResourcePolicyStorageUnavailable("resource policy storage failed") from exc

    missing = [key for key in specs if not resource_ids.get(key)]
    if missing:
        raise ResourcePolicyValidationError(f"required resource policies are not configured: {', '.join(missing)}")

    service_conn = None
    try:
        if any(spec.execution_scope == "service" for spec in specs.values()):
            from app.services.keystone import get_service_project_connection

            service_conn = await asyncio.to_thread(get_service_project_connection)
        resolved: dict[str, str] = {}
        for key, spec in specs.items():
            execution_conn = service_conn if spec.execution_scope == "service" else conn
            selected = await validate_existing_selection(execution_conn, key, resource_ids[key])
            resolved[key] = selected["id"]
        return resolved
    finally:
        if service_conn is not None:
            with suppress(Exception):
                await asyncio.to_thread(service_conn.close)
