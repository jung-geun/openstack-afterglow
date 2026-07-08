"""Focused regression tests for the worker runtime manager."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app import config as app_config
from app.config import Settings
from app.main import app
from app.models.worker_runtime import WorkerRuntimeStatus
from app.services import worker_runtime as runtime_service


@pytest.fixture
def isolated_worker_runtime_config(tmp_path, monkeypatch):
    """Load worker runtime defaults without ambient config or env overrides."""

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("WORKER_RUNTIME_"):
            monkeypatch.delenv(key, raising=False)
    app_config.load_raw_toml.cache_clear()
    app_config.get_settings.cache_clear()
    yield tmp_path
    app_config.load_raw_toml.cache_clear()
    app_config.get_settings.cache_clear()


@pytest.fixture
async def anon_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


class FakeDockerAPI:
    def __init__(self, containers: list[dict]) -> None:
        self.containers = [dict(container) for container in containers]
        self.deleted_ids: list[str] = []
        self.created: list[dict] = []
        self.started_ids: list[str] = []

    def _body(self, request: httpx.Request) -> dict:
        raw = request.content.decode("utf-8") if request.content else "{}"
        return json.loads(raw)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/_ping":
            return httpx.Response(200, request=request)

        if request.method == "GET" and request.url.path == "/containers/json":
            return httpx.Response(200, request=request, json=self.containers)

        if request.method == "DELETE" and request.url.path.startswith("/containers/"):
            container_id = request.url.path.split("/")[2]
            self.deleted_ids.append(container_id)
            self.containers = [container for container in self.containers if container["Id"] != container_id]
            return httpx.Response(204, request=request)

        if request.method == "POST" and request.url.path == "/containers/create":
            body = self._body(request)
            name = request.url.params["name"]
            container_id = f"created-{len(self.created)}"
            self.created.append({"name": name, "body": body})
            self.containers.append(
                {
                    "Id": container_id,
                    "Names": [f"/{name}"],
                    "State": "created",
                    "Labels": body["Labels"],
                }
            )
            return httpx.Response(201, request=request, json={"Id": container_id})

        if (
            request.method == "POST"
            and request.url.path.startswith("/containers/")
            and request.url.path.endswith("/start")
        ):
            container_id = request.url.path.split("/")[2]
            self.started_ids.append(container_id)
            for container in self.containers:
                if container["Id"] == container_id:
                    container["State"] = "running"
                    break
            return httpx.Response(204, request=request)

        raise AssertionError(f"Unexpected Docker request: {request.method} {request.url}")


def _worker_specs(settings: Settings | None = None) -> list[runtime_service.WorkerSpec]:
    return runtime_service.build_worker_specs(settings or Settings())


def _status(
    mode: str = "static", capable: bool = False, reason: str | None = "runtime_manager_disabled"
) -> WorkerRuntimeStatus:
    return WorkerRuntimeStatus(mode=mode, capable=capable, reason=reason, workers=[])


def _docker_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **overrides) -> runtime_service.DockerRuntimeConfig:
    socket_path = tmp_path / "docker.sock"
    socket_path.write_text("", encoding="utf-8")
    config_host_path = tmp_path / "afterglow.conf"
    config_host_path.write_text("[app]\nsite_name = 'Afterglow'\n", encoding="utf-8")
    logs_host_path = tmp_path / "logs"
    logs_host_path.mkdir()
    monkeypatch.setenv("AFTERGLOW_ALLOW_INSECURE", "1")
    base = runtime_service.DockerRuntimeConfig(
        socket_path=str(socket_path),
        image="afterglow/worker:latest",
        network="",
        config_mount="/app/afterglow.conf",
        config_host_path=str(config_host_path),
        gpu_config_mount="/app/config.gpu.toml",
        gpu_config_host_path="",
        logs_mount="/app/logs",
        logs_host_path=str(logs_host_path),
        env_allowlist=("AFTERGLOW_ALLOW_INSECURE",),
    )
    return replace(base, **overrides)


def _kubernetes_config(tmp_path: Path, **overrides) -> runtime_service.KubernetesRuntimeConfig:
    token_path = tmp_path / "token"
    token_path.write_text("token", encoding="utf-8")
    ca_path = tmp_path / "ca.crt"
    ca_path.write_text("ca", encoding="utf-8")
    base = runtime_service.KubernetesRuntimeConfig(
        namespace="afterglow",
        service_account_token_path=str(token_path),
        service_account_ca_path=str(ca_path),
        manage_deployments=False,
    )
    return replace(base, **overrides)


@pytest.mark.asyncio
async def test_worker_runtime_settings_default_to_static_with_single_replica_limits(isolated_worker_runtime_config):
    settings = app_config.get_settings()

    assert settings.worker_runtime_mode == "static"
    assert settings.worker_runtime_drover_desired_replicas == 1
    assert settings.worker_runtime_drover_max_replicas == 1
    assert settings.worker_runtime_notion_worker_desired_replicas == 1
    assert settings.worker_runtime_notion_worker_max_replicas == 1


@pytest.mark.asyncio
async def test_static_worker_runtime_adapter_reports_disabled_status():
    settings = Settings()
    specs = _worker_specs(settings)

    status = await runtime_service.StaticWorkerRuntimeAdapter().get_status(specs)

    assert status.mode == "static"
    assert status.capable is False
    assert status.reason == "runtime_manager_disabled"
    assert {worker.name for worker in status.workers} == {"drover", "notion_worker"}
    assert all(worker.mode == "static" for worker in status.workers)
    assert all(worker.capable is False for worker in status.workers)
    assert all(worker.reason == "runtime_manager_disabled" for worker in status.workers)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"socket_path": ""}, "docker_socket_not_configured"),
        ({"image": ""}, "docker_image_not_configured"),
        ({"config_host_path": ""}, "docker_mount_not_configured"),
        ({"env_allowlist": ("WORKER_RUNTIME_MISSING_ENV",)}, "docker_env_not_configured"),
    ],
)
async def test_docker_reconcile_returns_stable_unavailable_reasons_without_mutation(
    tmp_path, monkeypatch, overrides, expected_reason
):
    specs = _worker_specs(Settings())
    desired = runtime_service.desired_from_specs(specs)
    config = _docker_config(tmp_path, monkeypatch, **overrides)
    client = AsyncMock(spec=httpx.AsyncClient)
    adapter = runtime_service.DockerWorkerRuntimeAdapter(config, client=client)

    status = await adapter.reconcile(desired, specs)

    assert status.mode == "docker"
    assert status.capable is False
    assert status.reason == expected_reason
    assert all(worker.reason == expected_reason for worker in status.workers)
    client.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_docker_reconcile_recreates_lowest_missing_slot_and_ignores_static_containers(tmp_path, monkeypatch):
    config = _docker_config(tmp_path, monkeypatch)
    docker = FakeDockerAPI(
        [
            {
                "Id": "drover-running-0",
                "Names": ["/afterglow-managed-drover-0"],
                "State": "running",
                "Labels": {
                    "afterglow.worker-runtime.managed": "true",
                    "afterglow.worker": "drover",
                },
            },
            {
                "Id": "drover-exited-1",
                "Names": ["/afterglow-managed-drover-1"],
                "State": "exited",
                "Labels": {
                    "afterglow.worker-runtime.managed": "true",
                    "afterglow.worker": "drover",
                },
            },
            {
                "Id": "drover-running-2",
                "Names": ["/afterglow-managed-drover-2"],
                "State": "running",
                "Labels": {
                    "afterglow.worker-runtime.managed": "true",
                    "afterglow.worker": "drover",
                },
            },
            {
                "Id": "notion-running-0",
                "Names": ["/afterglow-managed-notion-worker-0"],
                "State": "running",
                "Labels": {
                    "afterglow.worker-runtime.managed": "true",
                    "afterglow.worker": "notion_worker",
                },
            },
            {
                "Id": "compose-drover-1",
                "Names": ["/drover"],
                "State": "running",
                "Labels": {},
            },
        ]
    )
    client = AsyncClient(transport=httpx.MockTransport(docker.handler), base_url="http://docker")
    adapter = runtime_service.DockerWorkerRuntimeAdapter(config, client=client)
    specs = [
        runtime_service.WorkerSpec(
            name="drover",
            module="app.worker",
            enabled=True,
            desired_replicas=3,
            max_replicas=3,
        ),
        runtime_service.WorkerSpec(
            name="notion_worker",
            module="app.notion_worker",
            enabled=True,
            desired_replicas=1,
            max_replicas=1,
        ),
    ]
    desired = runtime_service.desired_from_specs(specs)

    try:
        status = await adapter.reconcile(desired, specs)
    finally:
        await client.aclose()

    workers = {worker.name: worker for worker in status.workers}
    assert status.capable is True
    assert workers["drover"].observed_replicas == 3
    assert workers["notion_worker"].observed_replicas == 1
    assert docker.deleted_ids == ["drover-exited-1"]
    assert [item["name"] for item in docker.created] == ["afterglow-managed-drover-1"]
    assert docker.started_ids == ["created-0"]

    create_body = docker.created[0]["body"]
    assert create_body["Env"] == ["AFTERGLOW_ALLOW_INSECURE=1", "AFTERGLOW_ENV=production"]
    assert create_body["HostConfig"]["Binds"] == [
        f"{config.config_host_path}:{config.config_mount}:ro",
        f"{config.logs_host_path}:{config.logs_mount}",
    ]
    assert all(container_id != "compose-drover-1" for container_id in docker.deleted_ids)


@pytest.mark.asyncio
async def test_kubernetes_status_requires_service_account_token(tmp_path):
    missing = tmp_path / "missing-token"
    also_missing = tmp_path / "missing-ca"
    config = runtime_service.KubernetesRuntimeConfig(
        namespace="afterglow",
        service_account_token_path=str(missing),
        service_account_ca_path=str(also_missing),
        manage_deployments=False,
    )
    adapter = runtime_service.KubernetesWorkerRuntimeAdapter(config)

    status = await adapter.get_status(_worker_specs(Settings()))

    assert status.mode == "kubernetes"
    assert status.capable is False
    assert status.reason == "kubernetes_service_account_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_reason"),
    [
        (403, "kubernetes_rbac_forbidden"),
        (404, "kubernetes_deployment_not_found"),
    ],
)
async def test_kubernetes_status_maps_api_failures_to_stable_reasons(tmp_path, status_code, expected_reason):
    config = _kubernetes_config(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, request=request)

    client = AsyncClient(transport=httpx.MockTransport(handler), base_url="https://kubernetes.default.svc")
    adapter = runtime_service.KubernetesWorkerRuntimeAdapter(config, client=client)

    try:
        status = await adapter.get_status(_worker_specs(Settings()))
    finally:
        await client.aclose()

    assert status.mode == "kubernetes"
    assert status.capable is False
    assert status.reason == expected_reason


@pytest.mark.asyncio
async def test_kubernetes_reconcile_patches_only_scale_subresource(tmp_path):
    config = _kubernetes_config(tmp_path)
    observed: dict[str, int] = {"drover": 0, "notion-worker": 0}
    patch_calls: list[tuple[str, dict, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "PATCH":
            body = json.loads(request.content.decode("utf-8"))
            patch_calls.append((path, body, request.headers["content-type"]))
            deployment = path.rstrip("/").split("/")[-2]
            observed[deployment] = body["spec"]["replicas"]
            return httpx.Response(200, request=request, json={})

        if request.method == "GET":
            deployment = path.rstrip("/").split("/")[-1]
            return httpx.Response(
                200,
                request=request,
                json={"spec": {"replicas": observed[deployment]}, "status": {"replicas": observed[deployment]}},
            )

        raise AssertionError(f"Unexpected Kubernetes request: {request.method} {request.url}")

    client = AsyncClient(transport=httpx.MockTransport(handler), base_url="https://kubernetes.default.svc")
    adapter = runtime_service.KubernetesWorkerRuntimeAdapter(config, client=client)
    specs = [
        runtime_service.WorkerSpec(
            name="drover",
            module="app.worker",
            enabled=True,
            desired_replicas=1,
            max_replicas=4,
        ),
        runtime_service.WorkerSpec(
            name="notion_worker",
            module="app.notion_worker",
            enabled=True,
            desired_replicas=1,
            max_replicas=4,
        ),
    ]
    desired = [
        runtime_service.WorkerDesired(name="drover", desired_replicas=3),
        runtime_service.WorkerDesired(name="notion_worker", desired_replicas=2),
    ]

    try:
        status = await adapter.reconcile(desired, specs)
    finally:
        await client.aclose()

    assert status.capable is True
    assert [path for path, _, _ in patch_calls] == [
        "/apis/apps/v1/namespaces/afterglow/deployments/drover/scale",
        "/apis/apps/v1/namespaces/afterglow/deployments/notion-worker/scale",
    ]
    assert [body for _, body, _ in patch_calls] == [
        {"spec": {"replicas": 3}},
        {"spec": {"replicas": 2}},
    ]
    assert all(content_type == "application/merge-patch+json" for _, _, content_type in patch_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "body", "target"),
    [
        (
            "GET",
            "/api/v1/admin/worker-runtime/status",
            None,
            "app.api.identity.admin_worker_runtime.get_runtime_status",
        ),
        (
            "PATCH",
            "/api/v1/admin/worker-runtime/desired",
            {"workers": [{"name": "drover", "desired_replicas": 1}]},
            "app.api.identity.admin_worker_runtime.patch_desired_counts",
        ),
        (
            "POST",
            "/api/v1/admin/worker-runtime/reconcile",
            None,
            "app.api.identity.admin_worker_runtime.reconcile_once_with_lock",
        ),
    ],
)
async def test_worker_runtime_admin_routes_return_401_when_unauthenticated(anon_client, method, path, body, target):
    with patch(target, new=AsyncMock(return_value=_status())) as mocked:
        response = await anon_client.request(method, path, json=body)

    assert response.status_code == 401
    mocked.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "body", "target"),
    [
        (
            "GET",
            "/api/v1/admin/worker-runtime/status",
            None,
            "app.api.identity.admin_worker_runtime.get_runtime_status",
        ),
        (
            "PATCH",
            "/api/v1/admin/worker-runtime/desired",
            {"workers": [{"name": "drover", "desired_replicas": 1}]},
            "app.api.identity.admin_worker_runtime.patch_desired_counts",
        ),
        (
            "POST",
            "/api/v1/admin/worker-runtime/reconcile",
            None,
            "app.api.identity.admin_worker_runtime.reconcile_once_with_lock",
        ),
    ],
)
async def test_worker_runtime_admin_routes_return_403_for_non_admin(non_admin_client, method, path, body, target):
    with patch(target, new=AsyncMock(return_value=_status())) as mocked:
        response = await non_admin_client.request(method, path, json=body)

    assert response.status_code == 403
    mocked.assert_not_awaited()


@pytest.mark.asyncio
async def test_patch_worker_runtime_desired_rejects_counts_above_worker_max(admin_client):
    settings = Settings(worker_runtime_drover_max_replicas=1)
    with patch("app.services.worker_runtime.get_settings", return_value=settings):
        response = await admin_client.patch(
            "/api/v1/admin/worker-runtime/desired",
            json={"workers": [{"name": "drover", "desired_replicas": 2}]},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "drover desired_replicas exceeds max_replicas=1"


@pytest.mark.asyncio
async def test_reconcile_once_with_lock_skips_adapter_when_lock_is_not_acquired():
    settings = Settings(worker_runtime_mode="docker")

    with (
        patch("app.services.worker_runtime._acquire_reconcile_lock", new=AsyncMock(return_value=False)),
        patch("app.services.worker_runtime.get_adapter") as get_adapter,
        patch("app.services.worker_runtime._release_reconcile_lock", new=AsyncMock()) as release_lock,
    ):
        result = await runtime_service.reconcile_once_with_lock(settings)

    assert result is None
    get_adapter.assert_not_called()
    release_lock.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_once_with_lock_calls_adapter_after_lock_acquisition():
    settings = Settings(worker_runtime_mode="docker")
    specs = [
        runtime_service.WorkerSpec(
            name="drover",
            module="app.worker",
            enabled=True,
            desired_replicas=1,
            max_replicas=2,
        )
    ]
    desired = [runtime_service.WorkerDesired(name="drover", desired_replicas=1)]
    expected = WorkerRuntimeStatus(
        mode="docker",
        capable=True,
        reason=None,
        workers=[
            runtime_service.WorkerRuntimeWorkerStatus(
                name="drover",
                enabled=True,
                module="app.worker",
                desired_replicas=1,
                max_replicas=2,
                observed_replicas=1,
                mode="docker",
                capable=True,
                reason=None,
            )
        ],
    )
    adapter = AsyncMock()
    adapter.reconcile = AsyncMock(return_value=expected)

    with (
        patch("app.services.worker_runtime._acquire_reconcile_lock", new=AsyncMock(return_value=True)),
        patch("app.services.worker_runtime._release_reconcile_lock", new=AsyncMock()) as release_lock,
        patch("app.services.worker_runtime.build_worker_specs", return_value=specs),
        patch("app.services.worker_runtime.desired_with_overrides", new=AsyncMock(return_value=desired)),
        patch("app.services.worker_runtime.get_adapter", return_value=adapter),
    ):
        result = await runtime_service.reconcile_once_with_lock(settings)

    assert result == expected
    adapter.reconcile.assert_awaited_once_with(desired, specs)
    release_lock.assert_awaited_once()
