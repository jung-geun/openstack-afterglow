from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mcp_control_plane.container import (
    McpContainerError,
    get_project_container,
    list_project_containers,
    preview_project_container_action,
    request_project_container_action,
    request_project_container_delete,
)


class _Response:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


@pytest.mark.asyncio
async def test_container_list_requires_raw_owner_proof_and_redacts_environment():
    calls: list[tuple[str, object]] = []

    class Session:
        def get_endpoint(self, **kwargs):
            calls.append(("endpoint", kwargs))
            return "https://zun.example.test/v1"

        def get(self, path):
            calls.append(("get", path))
            return _Response(
                {
                    "containers": [
                        {
                            "uuid": "container-a",
                            "name": "web-a",
                            "status": "Running",
                            "image": "registry.example.test/web:1",
                            "created_at": "2026-07-27T00:00:00Z",
                            "project_id": "project-a",
                            "environment": {"PASSWORD": "secret"},
                            "addresses": {"private": [{"addr": "10.0.0.5"}]},
                        }
                    ]
                }
            )

    result = await list_project_containers(SimpleNamespace(session=Session()), project_id="project-a", limit=50)

    assert calls == [
        ("endpoint", {"service_type": "container", "interface": "public"}),
        ("get", "https://zun.example.test/v1/containers"),
    ]
    assert result == [
        {
            "id": "container-a",
            "name": "web-a",
            "status": "Running",
            "image": "registry.example.test/web:1",
            "created_at": "2026-07-27T00:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_container_get_rejects_foreign_owner_proof():
    class Session:
        def get_endpoint(self, **_kwargs):
            return "https://zun.example.test"

        def get(self, _path):
            return _Response(
                {
                    "container": {
                        "uuid": "container-a",
                        "name": "web-a",
                        "status": "Running",
                        "project_id": "project-b",
                    }
                }
            )

    with pytest.raises(McpContainerError, match="ownership"):
        await get_project_container(
            SimpleNamespace(session=Session()),
            project_id="project-a",
            container_id="container-a",
        )


@pytest.mark.asyncio
async def test_container_action_revalidates_owned_stopped_container_before_start():
    calls: list[tuple[str, object]] = []

    class Session:
        def get_endpoint(self, **kwargs):
            calls.append(("endpoint", kwargs))
            return "https://zun.example.test/v1"

        def get(self, path):
            calls.append(("get", path))
            return _Response(
                {
                    "container": {
                        "uuid": "container-a",
                        "name": "web-a",
                        "status": "Stopped",
                        "project_id": "project-a",
                    }
                }
            )

        def post(self, path):
            calls.append(("post", path))
            return None

    conn = SimpleNamespace(session=Session())
    preview = await preview_project_container_action(
        conn,
        project_id="project-a",
        container_id="container-a",
        action="start",
    )
    result = await request_project_container_action(
        conn,
        project_id="project-a",
        container_id="container-a",
        action="start",
    )

    assert preview["requested_action"] == "start"
    assert result["requested_action"] == "start"
    assert calls == [
        ("endpoint", {"service_type": "container", "interface": "public"}),
        ("get", "https://zun.example.test/v1/containers/container-a"),
        ("endpoint", {"service_type": "container", "interface": "public"}),
        ("get", "https://zun.example.test/v1/containers/container-a"),
        ("endpoint", {"service_type": "container", "interface": "public"}),
        ("post", "https://zun.example.test/v1/containers/container-a/start"),
    ]


@pytest.mark.asyncio
async def test_container_delete_rejects_running_container_before_provider_delete():
    calls: list[str] = []

    class Session:
        def get_endpoint(self, **_kwargs):
            return "https://zun.example.test"

        def get(self, _path):
            return _Response(
                {
                    "container": {
                        "uuid": "container-a",
                        "name": "web-a",
                        "status": "Running",
                        "project_id": "project-a",
                    }
                }
            )

        def delete(self, path):
            calls.append(path)
            return None

    with pytest.raises(McpContainerError, match="stopped"):
        await request_project_container_delete(
            SimpleNamespace(session=Session()),
            project_id="project-a",
            container_id="container-a",
        )

    assert calls == []
