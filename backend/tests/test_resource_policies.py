from types import SimpleNamespace

import pytest

from app.services import resource_policies


@pytest.mark.asyncio
async def test_external_network_policy_discovers_only_external_options(monkeypatch):
    monkeypatch.setattr(
        resource_policies.neutron,
        "list_networks",
        lambda _conn: [
            SimpleNamespace(id="private", name="private", is_external=False),
            SimpleNamespace(id="public", name="public", is_external=True),
        ],
    )

    options = await resource_policies.discover_options(object(), "k3s.occm_floating_network")

    assert options == [{"id": "public", "name": "public", "is_external": True, "is_shared": False}]
    assert await resource_policies.validate_selection(object(), "k3s.occm_floating_network", "public") == options[0]
    with pytest.raises(resource_policies.ResourcePolicyValidationError):
        await resource_policies.validate_selection(object(), "k3s.occm_floating_network", "private")


@pytest.mark.asyncio
async def test_service_scope_discovery_closes_owned_connection(monkeypatch):
    class ServiceConnection:
        closed = False

        def close(self):
            self.closed = True

    service_conn = ServiceConnection()
    admin_conn = object()

    async def service_connection(_admin_conn, spec):
        assert spec.execution_scope == "service"
        return service_conn

    monkeypatch.setattr(resource_policies, "discovery_connection", service_connection)
    monkeypatch.setattr(resource_policies.glance, "list_images", lambda _conn: [])

    assert await resource_policies.discover_options(admin_conn, "builder.image") == []
    assert service_conn.closed is True


@pytest.mark.asyncio
async def test_policy_clear_does_not_require_live_resource_lookup(monkeypatch):
    monkeypatch.setattr(resource_policies, "discover_options", lambda *_args: (_ for _ in ()).throw(AssertionError()))

    assert await resource_policies.validate_selection(object(), "builder.image", None) is None


def test_unknown_resource_policy_is_rejected():
    with pytest.raises(resource_policies.ResourcePolicyValidationError):
        resource_policies.get_spec("not-a-policy")
