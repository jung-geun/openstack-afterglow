from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mcp_control_plane.storage import (
    McpStorageError,
    get_project_backup,
    get_project_snapshot,
    get_project_volume,
    list_project_backups,
    list_project_server_volumes,
    list_project_snapshots,
    list_project_volumes,
    preview_project_backup_delete,
    preview_project_snapshot_delete,
    preview_project_volume_delete,
    request_project_backup_delete,
    request_project_snapshot_delete,
    request_project_volume_delete,
)


@pytest.mark.asyncio
async def test_volume_list_uses_project_filter_and_returns_only_safe_owned_fields():
    calls: list[dict[str, object]] = []

    class BlockStorage:
        def volumes(self, **kwargs):
            calls.append(kwargs)
            return [
                SimpleNamespace(
                    id="volume-a",
                    name="data-a",
                    status="available",
                    size=20,
                    project_id="project-a",
                    created_at="2026-07-27T00:00:00Z",
                    encryption_key_id="secret",
                    volume_image_metadata={"credential": "secret"},
                )
            ]

    result = await list_project_volumes(SimpleNamespace(block_storage=BlockStorage()), project_id="project-a", limit=50)

    assert calls == [{"details": True, "project_id": "project-a"}]
    assert result == [
        {
            "id": "volume-a",
            "name": "data-a",
            "status": "available",
            "size_gb": 20,
            "created_at": "2026-07-27T00:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_volume_get_requires_ownership_proof():
    class BlockStorage:
        def get_volume(self, _volume_id):
            return SimpleNamespace(id="volume-a", name=None, status="available", size=20, project_id="project-b")

    with pytest.raises(McpStorageError, match="ownership"):
        await get_project_volume(
            SimpleNamespace(block_storage=BlockStorage()), project_id="project-a", volume_id="volume-a"
        )


@pytest.mark.asyncio
async def test_snapshot_list_proves_snapshot_and_parent_volume_ownership_and_redacts_metadata():
    calls: list[tuple[str, object]] = []

    class BlockStorage:
        def snapshots(self, **kwargs):
            calls.append(("snapshots", kwargs))
            return [
                SimpleNamespace(
                    id="snapshot-a",
                    name="backup-a",
                    status="available",
                    size=20,
                    volume_id="volume-a",
                    project_id="project-a",
                    created_at="2026-07-27T00:00:00Z",
                    encryption_key_id="secret",
                    metadata={"credential": "secret"},
                )
            ]

        def get_volume(self, volume_id):
            calls.append(("get_volume", volume_id))
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="available",
                size=20,
                project_id="project-a",
            )

    result = await list_project_snapshots(
        SimpleNamespace(block_storage=BlockStorage()), project_id="project-a", limit=50
    )

    assert calls == [
        ("snapshots", {"details": True, "project_id": "project-a"}),
        ("get_volume", "volume-a"),
    ]
    assert result == [
        {
            "id": "snapshot-a",
            "name": "backup-a",
            "status": "available",
            "source_volume_id": "volume-a",
            "size_gb": 20,
            "created_at": "2026-07-27T00:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_snapshot_get_rejects_foreign_parent_volume():
    class BlockStorage:
        def get_snapshot(self, _snapshot_id):
            return SimpleNamespace(
                id="snapshot-a",
                name="backup-a",
                status="available",
                size=20,
                volume_id="volume-a",
                project_id="project-a",
            )

        def get_volume(self, volume_id):
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="available",
                size=20,
                project_id="project-b",
            )

    with pytest.raises(McpStorageError, match="ownership"):
        await get_project_snapshot(
            SimpleNamespace(block_storage=BlockStorage()),
            project_id="project-a",
            snapshot_id="snapshot-a",
        )


@pytest.mark.asyncio
async def test_backup_list_proves_parent_ownership_and_redacts_metadata():
    calls: list[tuple[str, object]] = []

    class BlockStorage:
        def backups(self, **kwargs):
            calls.append(("backups", kwargs))
            return [
                SimpleNamespace(
                    id="backup-a",
                    name="daily-a",
                    status="available",
                    size=20,
                    volume_id="volume-a",
                    project_id="project-a",
                    created_at="2026-07-27T00:00:00Z",
                    service_metadata={"credential": "secret"},
                )
            ]

        def get_volume(self, volume_id):
            calls.append(("get_volume", volume_id))
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="available",
                size=20,
                project_id="project-a",
            )

    result = await list_project_backups(SimpleNamespace(block_storage=BlockStorage()), project_id="project-a", limit=50)

    assert calls == [
        ("backups", {"details": True, "project_id": "project-a"}),
        ("get_volume", "volume-a"),
    ]
    assert result == [
        {
            "id": "backup-a",
            "name": "daily-a",
            "status": "available",
            "source_volume_id": "volume-a",
            "size_gb": 20,
            "created_at": "2026-07-27T00:00:00Z",
        }
    ]


@pytest.mark.asyncio
async def test_backup_get_rejects_foreign_backup_record():
    class BlockStorage:
        def get_backup(self, _backup_id):
            return SimpleNamespace(
                id="backup-a",
                name="daily-a",
                status="available",
                size=20,
                volume_id="volume-a",
                project_id="project-b",
            )

    with pytest.raises(McpStorageError, match="ownership"):
        await get_project_backup(
            SimpleNamespace(block_storage=BlockStorage()),
            project_id="project-a",
            backup_id="backup-a",
        )


@pytest.mark.asyncio
async def test_volume_delete_revalidates_available_owner_without_force():
    calls: list[tuple[str, object]] = []

    class BlockStorage:
        def get_volume(self, volume_id):
            calls.append(("get_volume", volume_id))
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="available",
                size=20,
                project_id="project-a",
            )

        def delete_volume(self, volume_id, **kwargs):
            calls.append(("delete_volume", (volume_id, kwargs)))

    conn = SimpleNamespace(block_storage=BlockStorage())
    preview = await preview_project_volume_delete(conn, project_id="project-a", volume_id="volume-a")
    result = await request_project_volume_delete(conn, project_id="project-a", volume_id="volume-a")

    assert preview["requested_action"] == "delete"
    assert result["requested_action"] == "delete"
    assert calls == [
        ("get_volume", "volume-a"),
        ("get_volume", "volume-a"),
        ("delete_volume", ("volume-a", {"ignore_missing": False, "force": False})),
    ]


@pytest.mark.asyncio
async def test_volume_delete_rejects_in_use_state_before_provider_call():
    calls: list[str] = []

    class BlockStorage:
        def get_volume(self, volume_id):
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="in-use",
                size=20,
                project_id="project-a",
            )

        def delete_volume(self, volume_id, **_kwargs):
            calls.append(volume_id)

    with pytest.raises(McpStorageError, match="state"):
        await request_project_volume_delete(
            SimpleNamespace(block_storage=BlockStorage()),
            project_id="project-a",
            volume_id="volume-a",
        )

    assert calls == []


@pytest.mark.asyncio
async def test_vm_volume_list_proves_owned_parent_attachment_and_child_volume():
    calls: list[tuple[str, object]] = []

    class Compute:
        def get_server(self, server_id):
            calls.append(("get_server", server_id))
            return SimpleNamespace(id=server_id, name="web-a", status="ACTIVE", project_id="project-a")

        def volume_attachments(self, server_id):
            calls.append(("volume_attachments", server_id))
            return [SimpleNamespace(volume_id="volume-a", device="/dev/vdb")]

    class BlockStorage:
        def get_volume(self, volume_id):
            calls.append(("get_volume", volume_id))
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="in-use",
                size=20,
                project_id="project-a",
                encryption_key_id="secret",
            )

    result = await list_project_server_volumes(
        SimpleNamespace(compute=Compute(), block_storage=BlockStorage()),
        project_id="project-a",
        server_id="server-a",
        limit=50,
    )

    assert result == [
        {
            "id": "volume-a",
            "name": "data-a",
            "status": "in-use",
            "size_gb": 20,
            "created_at": None,
        }
    ]
    assert calls == [
        ("get_server", "server-a"),
        ("volume_attachments", "server-a"),
        ("get_volume", "volume-a"),
    ]


@pytest.mark.asyncio
async def test_vm_volume_list_rejects_foreign_child_volume():
    class Compute:
        def get_server(self, server_id):
            return SimpleNamespace(id=server_id, name="web-a", status="ACTIVE", project_id="project-a")

        def volume_attachments(self, _server_id):
            return [SimpleNamespace(volume_id="volume-a")]

    class BlockStorage:
        def get_volume(self, volume_id):
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="in-use",
                size=20,
                project_id="project-b",
            )

    with pytest.raises(McpStorageError, match="ownership"):
        await list_project_server_volumes(
            SimpleNamespace(compute=Compute(), block_storage=BlockStorage()),
            project_id="project-a",
            server_id="server-a",
            limit=50,
        )


@pytest.mark.asyncio
async def test_snapshot_and_backup_delete_revalidate_owned_parent_without_force():
    calls: list[tuple[str, object]] = []

    class BlockStorage:
        def get_snapshot(self, snapshot_id):
            calls.append(("get_snapshot", snapshot_id))
            return SimpleNamespace(
                id=snapshot_id,
                name="snapshot-a",
                status="available",
                size=20,
                volume_id="volume-a",
                project_id="project-a",
            )

        def get_backup(self, backup_id):
            calls.append(("get_backup", backup_id))
            return SimpleNamespace(
                id=backup_id,
                name="backup-a",
                status="available",
                size=20,
                volume_id="volume-a",
                project_id="project-a",
            )

        def get_volume(self, volume_id):
            calls.append(("get_volume", volume_id))
            return SimpleNamespace(
                id=volume_id,
                name="data-a",
                status="available",
                size=20,
                project_id="project-a",
            )

        def delete_snapshot(self, snapshot_id, **kwargs):
            calls.append(("delete_snapshot", (snapshot_id, kwargs)))

        def delete_backup(self, backup_id, **kwargs):
            calls.append(("delete_backup", (backup_id, kwargs)))

    conn = SimpleNamespace(block_storage=BlockStorage())
    snapshot_preview = await preview_project_snapshot_delete(
        conn,
        project_id="project-a",
        snapshot_id="snapshot-a",
    )
    snapshot_result = await request_project_snapshot_delete(
        conn,
        project_id="project-a",
        snapshot_id="snapshot-a",
    )
    backup_preview = await preview_project_backup_delete(
        conn,
        project_id="project-a",
        backup_id="backup-a",
    )
    backup_result = await request_project_backup_delete(
        conn,
        project_id="project-a",
        backup_id="backup-a",
    )

    assert snapshot_preview["requested_action"] == "delete"
    assert snapshot_result["requested_action"] == "delete"
    assert backup_preview["requested_action"] == "delete"
    assert backup_result["requested_action"] == "delete"
    assert calls == [
        ("get_snapshot", "snapshot-a"),
        ("get_volume", "volume-a"),
        ("get_snapshot", "snapshot-a"),
        ("get_volume", "volume-a"),
        ("delete_snapshot", ("snapshot-a", {"ignore_missing": False, "force": False})),
        ("get_backup", "backup-a"),
        ("get_volume", "volume-a"),
        ("get_backup", "backup-a"),
        ("get_volume", "volume-a"),
        ("delete_backup", ("backup-a", {"ignore_missing": False, "force": False})),
    ]
