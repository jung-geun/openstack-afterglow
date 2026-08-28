import pytest

from app.services import resource_policies


class _NetworkAPI:
    def __init__(self, networks):
        self._networks = {network.id: network for network in networks}

    def get_network(self, resource_id):
        return self._networks.get(resource_id)


class _NetworkConnection:
    def __init__(self, networks):
        self.network = _NetworkAPI(networks)


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
    monkeypatch.setattr(resource_policies.nova, "list_flavors", lambda _conn: [])

    assert await resource_policies.discover_options(admin_conn, "builder.flavor") == []
    assert service_conn.closed is True


@pytest.mark.asyncio
async def test_policy_clear_does_not_require_live_resource_lookup(monkeypatch):
    monkeypatch.setattr(
        resource_policies, "validate_existing_selection", lambda *_args: (_ for _ in ()).throw(AssertionError())
    )

    assert await resource_policies.validate_selection(object(), "builder.flavor", None) is None


@pytest.mark.asyncio
async def test_legacy_name_selector_resolves_one_exact_catalog_name(monkeypatch):
    def unavailable(*_args):
        raise resource_policies.ResourcePolicyValidationError("ID not found")

    monkeypatch.setattr(resource_policies, "_validate_existing_sync", unavailable)
    monkeypatch.setattr(
        resource_policies,
        "_discover_sync",
        lambda _conn, _spec: [
            {"id": "type-cephfs", "name": "cephfs"},
            {"id": "type-nfs", "name": "nfs"},
        ],
    )

    assert await resource_policies.validate_legacy_selection(
        object(), "manila.cephfs_share_type", "cephfs", allow_exact_name=True
    ) == {"id": "type-cephfs", "name": "cephfs"}


@pytest.mark.asyncio
async def test_legacy_name_selector_rejects_ambiguous_or_disallowed_names(monkeypatch):
    monkeypatch.setattr(
        resource_policies,
        "_validate_existing_sync",
        lambda *_args: (_ for _ in ()).throw(resource_policies.ResourcePolicyValidationError("ID not found")),
    )
    monkeypatch.setattr(
        resource_policies,
        "_discover_sync",
        lambda _conn, _spec: [{"id": "first", "name": "cephfs"}, {"id": "second", "name": "cephfs"}],
    )

    with pytest.raises(resource_policies.ResourcePolicyValidationError, match="ambiguous"):
        await resource_policies.validate_legacy_selection(
            object(), "manila.cephfs_share_type", "cephfs", allow_exact_name=True
        )
    with pytest.raises(resource_policies.ResourcePolicyValidationError):
        await resource_policies.validate_legacy_selection(
            object(), "manila.cephfs_share_type", "cephfs", allow_exact_name=False
        )


def test_registry_has_no_service_owned_drover_policies():
    keys = {spec.key for spec in resource_policies.list_specs()}

    assert not any(key.startswith("k3s.") for key in keys)
    assert {"openstack.service_project", "cinder.default_volume_availability_zone", "manila.nfs_share_type"} <= keys


def test_unknown_resource_policy_is_rejected():
    with pytest.raises(resource_policies.ResourcePolicyValidationError):
        resource_policies.get_spec("not-a-policy")
