from __future__ import annotations

import pytest

from app.api.compute import instances
from app.models.compute import CreateCloudInitPresetRequest


@pytest.mark.asyncio
async def test_cloud_init_library_is_scoped_to_authenticated_user(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def list_snippets(user_id: str) -> dict:
        seen.append(user_id)
        return {"history": [], "presets": []}

    monkeypatch.setattr(instances.vm_cloud_init_library, "list_snippets", list_snippets)

    result = await instances.list_cloud_init_library({"user_id": "user-a"})

    assert result == {"history": [], "presets": []}
    assert seen == ["user-a"]


@pytest.mark.asyncio
async def test_cloud_init_preset_uses_authenticated_user(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    async def create_preset(**kwargs: object) -> dict:
        captured.update(kwargs)
        return {"id": 1, "kind": "preset", "name": "bootstrap", "content": "#cloud-config"}

    monkeypatch.setattr(instances.vm_cloud_init_library, "create_preset", create_preset)

    async def noop(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(instances, "invalidate", noop)
    monkeypatch.setattr(instances.cache_invalidation, "invalidate_mutation_count", noop)

    result = await instances.save_cloud_init_preset(
        CreateCloudInitPresetRequest(name="bootstrap", content="#cloud-config"),
        {"user_id": "user-a", "project_id": "project-a"},
    )

    assert result["name"] == "bootstrap"
    assert captured == {"user_id": "user-a", "name": "bootstrap", "content": "#cloud-config"}


@pytest.mark.asyncio
async def test_history_write_failure_does_not_fail_created_vm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def record_history(**_: object) -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(instances.vm_cloud_init_library, "record_history", record_history)

    await instances._record_cloud_init_history_best_effort({"user_id": "user-a"}, "#cloud-config")
