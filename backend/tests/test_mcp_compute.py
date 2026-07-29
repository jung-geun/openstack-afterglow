from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mcp_control_plane.compute import (
    McpComputeError,
    get_project_server,
    list_project_server_interfaces,
    list_project_servers,
    preview_project_server_action,
    preview_project_server_delete,
    project_server_overview,
    request_project_server_action,
    request_project_server_delete,
)


@pytest.mark.asyncio
async def test_vm_list_filters_provider_query_and_returns_only_safe_owned_fields():
    calls: list[dict[str, object]] = []

    class Compute:
        def servers(self, **kwargs):
            calls.append(kwargs)
            return [
                SimpleNamespace(
                    id="server-a",
                    name="web-a",
                    status="ACTIVE",
                    project_id="project-a",
                    created_at="2026-07-27T00:00:00Z",
                    updated_at="2026-07-27T00:01:00Z",
                    admin_password="secret",
                    console_url="https://private.example.test/console",
                )
            ]

    result = await list_project_servers(SimpleNamespace(compute=Compute()), project_id="project-a", limit=50)

    assert calls == [{"details": True, "project_id": "project-a"}]
    assert result == [
        {
            "id": "server-a",
            "name": "web-a",
            "status": "ACTIVE",
            "created_at": "2026-07-27T00:00:00Z",
            "updated_at": "2026-07-27T00:01:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_vm_list_denies_missing_or_foreign_ownership_proof():
    class Compute:
        def servers(self, **_kwargs):
            return [SimpleNamespace(id="server-b", name="web-b", status="ACTIVE", project_id="project-b")]

    with pytest.raises(McpComputeError, match="ownership"):
        await list_project_servers(SimpleNamespace(compute=Compute()), project_id="project-a", limit=50)


@pytest.mark.asyncio
async def test_vm_get_proves_owner_and_omits_sensitive_provider_fields():
    calls: list[str] = []

    class Compute:
        def get_server(self, server_id):
            calls.append(server_id)
            return SimpleNamespace(
                id=server_id,
                name="web-a",
                status="ACTIVE",
                tenant_id="project-a",
                created="2026-07-27T00:00:00Z",
                updated="2026-07-27T00:01:00Z",
                admin_pass="secret",
                metadata={"credential": "secret"},
            )

    result = await get_project_server(
        SimpleNamespace(compute=Compute()),
        project_id="project-a",
        server_id="12345678-1234-1234-1234-123456789abc",
    )

    assert calls == ["12345678-1234-1234-1234-123456789abc"]
    assert result == {
        "id": "12345678-1234-1234-1234-123456789abc",
        "name": "web-a",
        "status": "ACTIVE",
        "created_at": "2026-07-27T00:00:00Z",
        "updated_at": "2026-07-27T00:01:00Z",
    }


@pytest.mark.asyncio
async def test_vm_action_previews_and_dispatches_only_owned_allowed_state():
    calls: list[tuple[str, object]] = []

    class Compute:
        def get_server(self, server_id):
            calls.append(("get_server", server_id))
            return SimpleNamespace(
                id=server_id,
                name="web-a",
                status="ACTIVE",
                project_id="project-a",
                created_at="2026-07-27T00:00:00Z",
                updated_at="2026-07-27T00:01:00Z",
            )

        def stop_server(self, server_id):
            calls.append(("stop_server", server_id))

    conn = SimpleNamespace(compute=Compute())

    preview = await preview_project_server_action(
        conn,
        project_id="project-a",
        server_id="server-a",
        action="stop",
    )
    result = await request_project_server_action(
        conn,
        project_id="project-a",
        server_id="server-a",
        action="stop",
    )

    assert preview["requested_action"] == "stop"
    assert result["requested_action"] == "stop"
    assert calls == [
        ("get_server", "server-a"),
        ("get_server", "server-a"),
        ("stop_server", "server-a"),
    ]


@pytest.mark.asyncio
async def test_vm_action_rejects_foreign_or_invalid_state_before_provider_call():
    calls: list[str] = []

    class Compute:
        def get_server(self, server_id):
            return SimpleNamespace(id=server_id, name="web-a", status="SHUTOFF", project_id="project-a")

        def stop_server(self, server_id):
            calls.append(server_id)

    with pytest.raises(McpComputeError, match="state"):
        await request_project_server_action(
            SimpleNamespace(compute=Compute()),
            project_id="project-a",
            server_id="server-a",
            action="stop",
        )

    assert calls == []


@pytest.mark.asyncio
async def test_cloud_overview_counts_only_exact_project_provider_records():
    calls: list[dict[str, object]] = []

    class Compute:
        def servers(self, **kwargs):
            calls.append(kwargs)
            return [
                SimpleNamespace(id="server-active", name="a", status="ACTIVE", project_id="project-a"),
                SimpleNamespace(id="server-off", name="b", status="SHUTOFF", project_id="project-a"),
                SimpleNamespace(id="server-error", name="c", status="ERROR", project_id="project-a"),
            ]

    result = await project_server_overview(SimpleNamespace(compute=Compute()), project_id="project-a")

    assert calls == [{"details": True, "project_id": "project-a"}]
    assert result == {"total": 3, "active": 1, "shutoff": 1, "error": 1}


@pytest.mark.asyncio
async def test_vm_delete_previews_and_deletes_only_owned_server_without_force():
    calls: list[tuple[str, object]] = []

    class Compute:
        def get_server(self, server_id):
            calls.append(("get_server", server_id))
            return SimpleNamespace(
                id=server_id,
                name="web-a",
                status="SHUTOFF",
                project_id="project-a",
                created_at="2026-07-27T00:00:00Z",
                updated_at="2026-07-27T00:01:00Z",
            )

        def delete_server(self, server_id, **kwargs):
            calls.append(("delete_server", (server_id, kwargs)))

    conn = SimpleNamespace(compute=Compute())

    preview = await preview_project_server_delete(conn, project_id="project-a", server_id="server-a")
    result = await request_project_server_delete(conn, project_id="project-a", server_id="server-a")

    assert preview["requested_action"] == "delete"
    assert result["requested_action"] == "delete"
    assert calls == [
        ("get_server", "server-a"),
        ("get_server", "server-a"),
        ("delete_server", ("server-a", {"ignore_missing": False, "force": False})),
    ]


@pytest.mark.asyncio
async def test_vm_interfaces_require_owned_server_and_each_attached_port():
    calls: list[tuple[str, object]] = []

    class Compute:
        def get_server(self, server_id):
            calls.append(("get_server", server_id))
            return SimpleNamespace(id=server_id, name="web-a", status="ACTIVE", project_id="project-a")

        def server_interfaces(self, server_id):
            calls.append(("server_interfaces", server_id))
            return [SimpleNamespace(port_id="port-a", mac_addr="fa:16:3e:00:00:01")]

    class Network:
        def get_port(self, port_id):
            calls.append(("get_port", port_id))
            return SimpleNamespace(id=port_id, project_id="project-a", fixed_ips=[{"ip_address": "10.0.0.5"}])

    result = await list_project_server_interfaces(
        SimpleNamespace(compute=Compute(), network=Network()),
        project_id="project-a",
        server_id="server-a",
        limit=50,
    )

    assert result == [{"port_id": "port-a", "mac_address": "fa:16:3e:00:00:01"}]
    assert calls == [
        ("get_server", "server-a"),
        ("server_interfaces", "server-a"),
        ("get_port", "port-a"),
    ]


@pytest.mark.asyncio
async def test_vm_interfaces_reject_foreign_attached_port():
    calls: list[str] = []

    class Compute:
        def get_server(self, server_id):
            return SimpleNamespace(id=server_id, name="web-a", status="ACTIVE", project_id="project-a")

        def server_interfaces(self, _server_id):
            return [SimpleNamespace(port_id="port-a", mac_addr="fa:16:3e:00:00:01")]

    class Network:
        def get_port(self, port_id):
            calls.append(port_id)
            return SimpleNamespace(id=port_id, project_id="project-b")

    with pytest.raises(McpComputeError, match="port ownership"):
        await list_project_server_interfaces(
            SimpleNamespace(compute=Compute(), network=Network()),
            project_id="project-a",
            server_id="server-a",
            limit=50,
        )

    assert calls == ["port-a"]
