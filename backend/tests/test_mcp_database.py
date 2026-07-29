from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mcp_control_plane.database import (
    McpDatabaseError,
    get_project_database_instance,
    list_project_database_instances,
    preview_project_database_instance_delete,
    preview_project_database_instance_restart,
    request_project_database_instance_delete,
    request_project_database_instance_restart,
)


class _Response:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_database_list_returns_only_closed_owned_fields():
    calls: list[str] = []

    class Database:
        def get(self, path):
            calls.append(path)
            return _Response(
                {
                    "instances": [
                        {
                            "id": "database-a",
                            "name": "postgres-a",
                            "status": "ACTIVE",
                            "datastore": {"type": "postgresql", "version": "16"},
                            "created": "2026-07-27T00:00:00Z",
                            "ip": ["10.0.0.5"],
                            "links": [{"href": "https://private.example.test"}],
                        }
                    ]
                }
            )

    result = await list_project_database_instances(
        SimpleNamespace(database=Database(), _afterglow_project_id="project-a"),
        project_id="project-a",
        limit=50,
    )

    assert calls == ["/instances"]
    assert result == [
        {
            "id": "database-a",
            "name": "postgres-a",
            "status": "ACTIVE",
            "datastore_type": "postgresql",
            "datastore_version": "16",
            "created_at": "2026-07-27T00:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_database_get_rejects_unproven_connection_scope_before_provider_call():
    calls: list[str] = []

    class Database:
        def get(self, path):
            calls.append(path)
            return _Response(
                {
                    "instance": {
                        "id": "database-a",
                        "name": "postgres-a",
                        "status": "ACTIVE",
                        "datastore": {"type": "postgresql", "version": "16"},
                    }
                }
            )

    with pytest.raises(McpDatabaseError, match="connection project scope"):
        await get_project_database_instance(
            SimpleNamespace(database=Database(), _afterglow_project_id="project-b"),
            project_id="project-a",
            instance_id="database-a",
        )

    assert calls == []


@pytest.mark.asyncio
async def test_database_restart_and_delete_revalidate_scoped_instance_before_dispatch():
    calls: list[tuple[str, object]] = []

    class Database:
        def get(self, path):
            calls.append(("get", path))
            return _Response(
                {
                    "instance": {
                        "id": "database-a",
                        "name": "postgres-a",
                        "status": "ACTIVE",
                        "datastore": {"type": "postgresql", "version": "16"},
                    }
                }
            )

        def post(self, path, *, json):
            calls.append(("post", (path, json)))
            return None

        def delete(self, path):
            calls.append(("delete", path))
            return None

    conn = SimpleNamespace(database=Database(), _afterglow_project_id="project-a")
    restart_preview = await preview_project_database_instance_restart(
        conn,
        project_id="project-a",
        instance_id="database-a",
    )
    restart_result = await request_project_database_instance_restart(
        conn,
        project_id="project-a",
        instance_id="database-a",
    )
    delete_preview = await preview_project_database_instance_delete(
        conn,
        project_id="project-a",
        instance_id="database-a",
    )
    delete_result = await request_project_database_instance_delete(
        conn,
        project_id="project-a",
        instance_id="database-a",
    )

    assert restart_preview["requested_action"] == "restart"
    assert restart_result["requested_action"] == "restart"
    assert delete_preview["requested_action"] == "delete"
    assert delete_result["requested_action"] == "delete"
    assert calls == [
        ("get", "/instances/database-a"),
        ("get", "/instances/database-a"),
        ("post", ("/instances/database-a/action", {"restart": {}})),
        ("get", "/instances/database-a"),
        ("get", "/instances/database-a"),
        ("delete", "/instances/database-a"),
    ]
