"""볼륨 삭제 진단/복구 서비스의 계약 테스트."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from openstack.exceptions import ResourceNotFound

from app.services import cinder, volume_delete_recovery
from tests.conftest import make_mock_conn


def _make_volume(
    status: str | None,
    *,
    attachments: list[dict] | None = None,
    project_id: str | None = "proj-1",
):
    return SimpleNamespace(
        status=status,
        attachments=attachments or [],
        project_id=project_id,
    )


def _messages_response(messages: list[dict]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"messages": messages}
    return response


def test_diagnose_volume_delete_issue_marks_unattached_error_deleting_recoverable():
    conn = make_mock_conn()
    conn.block_storage.get_volume.return_value = _make_volume("error_deleting")
    conn.block_storage.get_endpoint.return_value = "http://cinder"
    conn.session.get.return_value = _messages_response([])

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
    ):
        diagnostic = volume_delete_recovery.diagnose_volume_delete_issue(conn, "vol-1")

    assert diagnostic.root_cause_code == "recoverable_error_deleting"
    assert diagnostic.recovery_available is True
    assert diagnostic.force_delete_available is True
    assert diagnostic.evidence == ["status=error_deleting"]


def test_recover_delete_volume_attached_blocker_skips_mutations():
    conn = make_mock_conn()
    conn.block_storage.get_volume.return_value = _make_volume(
        "error_deleting",
        attachments=[{"server_id": "srv-1", "device": "/dev/vdb"}],
    )

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status") as reset_mock,
        patch("app.services.volume_delete_recovery.cinder.delete_volume") as delete_mock,
        patch("app.services.volume_delete_recovery.cinder.force_delete_volume") as force_mock,
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1")

    assert result.status == "blocked"
    assert result.verified_deleted is False
    assert result.diagnostic.root_cause_code == "attached_volume_delete_blocked"
    assert "attachment:srv-1:/dev/vdb" in result.diagnostic.evidence
    reset_mock.assert_not_called()
    delete_mock.assert_not_called()
    force_mock.assert_not_called()


def test_recover_delete_volume_dependency_blocker_lists_ids_and_skips_mutations():
    conn = make_mock_conn()
    conn.block_storage.get_volume.return_value = _make_volume("error_deleting")

    snapshots = [{"id": "snap-1", "status": "available", "name": "snap-a"}]
    backups = [
        {"id": "backup-1", "status": "creating", "name": "backup-a", "volume_id": "vol-1"},
        {"id": "backup-2", "status": "deleted", "name": "backup-deleted", "volume_id": "vol-1"},
    ]

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=snapshots),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=backups),
        patch("app.services.volume_delete_recovery.cinder.delete_snapshot") as delete_snapshot_mock,
        patch("app.services.volume_delete_recovery.cinder.delete_backup") as delete_backup_mock,
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status") as reset_mock,
        patch("app.services.volume_delete_recovery.cinder.delete_volume") as delete_mock,
        patch("app.services.volume_delete_recovery.cinder.force_delete_volume") as force_mock,
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1")

    assert result.status == "blocked"
    assert result.diagnostic.root_cause_code == "dependent_snapshot_or_backup"
    assert {(dep.kind, dep.id) for dep in result.diagnostic.dependencies} == {
        ("snapshot", "snap-1"),
        ("backup", "backup-1"),
    }
    delete_snapshot_mock.assert_not_called()
    delete_backup_mock.assert_not_called()
    reset_mock.assert_not_called()
    delete_mock.assert_not_called()
    force_mock.assert_not_called()


def test_missing_volume_returns_already_deleted_diagnostic_and_recovery():
    conn = make_mock_conn()
    conn.block_storage.get_volume.side_effect = ResourceNotFound()

    diagnostic = volume_delete_recovery.diagnose_volume_delete_issue(conn, "vol-gone")
    result = volume_delete_recovery.recover_delete_volume(conn, "vol-gone")

    assert diagnostic.root_cause_code == "already_deleted"
    assert diagnostic.evidence == ["volume_not_found"]
    assert result.status == "already_deleted"
    assert result.verified_deleted is True
    assert result.final_status is None


def test_recover_delete_volume_happy_path_resets_then_deletes_and_verifies_absent():
    conn = make_mock_conn()
    conn.block_storage.get_volume.side_effect = [
        _make_volume("error_deleting"),
        ResourceNotFound(),
    ]

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status") as reset_mock,
        patch("app.services.volume_delete_recovery.cinder.delete_volume") as delete_mock,
        patch("app.services.volume_delete_recovery.cinder.force_delete_volume") as force_mock,
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1", verify_timeout_seconds=0)

    assert result.status == "deleted"
    assert result.verified_deleted is True
    assert result.final_status is None
    reset_mock.assert_called_once_with(conn, "vol-1", "error", "detached")
    delete_mock.assert_called_once_with(conn, "vol-1")
    force_mock.assert_not_called()


def test_recover_delete_volume_delete_timeout_falls_back_to_force_and_verifies():
    conn = make_mock_conn()
    conn.block_storage.get_volume.side_effect = [
        _make_volume("error_deleting"),
        _make_volume("deleting"),
        ResourceNotFound(),
    ]

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status"),
        patch("app.services.volume_delete_recovery.cinder.delete_volume") as delete_mock,
        patch("app.services.volume_delete_recovery.cinder.force_delete_volume") as force_mock,
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1", verify_timeout_seconds=0)

    assert result.status == "deleted"
    assert result.verified_deleted is True
    assert any(
        step.action == "verify_after_delete" and step.detail == "still_present:deleting" for step in result.steps
    )
    delete_mock.assert_called_once_with(conn, "vol-1")
    force_mock.assert_called_once_with(conn, "vol-1")


def test_recover_delete_volume_delete_failure_falls_back_to_force_and_verifies():
    conn = make_mock_conn()
    conn.block_storage.get_volume.side_effect = [
        _make_volume("error_deleting"),
        ResourceNotFound(),
    ]

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status"),
        patch(
            "app.services.volume_delete_recovery.cinder.delete_volume",
            side_effect=RuntimeError("normal delete failed"),
        ) as delete_mock,
        patch("app.services.volume_delete_recovery.cinder.force_delete_volume") as force_mock,
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1", verify_timeout_seconds=0)

    assert result.status == "deleted"
    assert result.verified_deleted is True
    assert any(step.action == "delete" and step.status == "failed" for step in result.steps)
    delete_mock.assert_called_once_with(conn, "vol-1")
    force_mock.assert_called_once_with(conn, "vol-1")


def test_recover_delete_volume_force_submit_without_absence_returns_delete_submitted():
    conn = make_mock_conn()
    conn.block_storage.get_volume.side_effect = [
        _make_volume("error_deleting"),
        _make_volume("deleting"),
        _make_volume("error_deleting"),
    ]

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status"),
        patch("app.services.volume_delete_recovery.cinder.delete_volume"),
        patch("app.services.volume_delete_recovery.cinder.force_delete_volume") as force_mock,
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1", verify_timeout_seconds=0)

    assert result.status == "delete_submitted"
    assert result.verified_deleted is False
    assert result.final_status == "error_deleting"
    assert any(
        step.action == "verify_after_force_delete" and step.detail == "still_present:error_deleting"
        for step in result.steps
    )
    force_mock.assert_called_once_with(conn, "vol-1")


def test_recover_delete_volume_force_delete_exception_is_sanitized():
    conn = make_mock_conn()
    conn.block_storage.get_volume.return_value = _make_volume("error_deleting")
    long_message = "x" * 250

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.reset_volume_status"),
        patch(
            "app.services.volume_delete_recovery.cinder.delete_volume",
            side_effect=RuntimeError("normal delete failed"),
        ),
        patch(
            "app.services.volume_delete_recovery.cinder.force_delete_volume",
            side_effect=ValueError(long_message),
        ),
    ):
        result = volume_delete_recovery.recover_delete_volume(conn, "vol-1")

    assert result.status == "failed"
    force_step = next(step for step in result.steps if step.action == "force_delete")
    assert force_step.status == "failed"
    assert force_step.detail == f"ValueError: {long_message[:200]}"


def test_diagnose_volume_delete_issue_filters_messages_by_volume_resource():
    conn = make_mock_conn()
    conn.block_storage.get_volume.return_value = _make_volume("error_deleting")
    conn.block_storage.get_endpoint.return_value = "http://cinder"
    conn.session.get.return_value = _messages_response(
        [
            {
                "id": "msg-1",
                "event_id": "event-1",
                "request_id": "req-1",
                "message_level": "ERROR",
                "resource_uuid": "vol-1",
                "resource_type": "volume",
                "user_message": "Primary volume delete blocker",
                "created_at": "2026-07-07T00:00:00Z",
            },
            {
                "id": "msg-2",
                "event_id": "event-2",
                "request_id": "req-2",
                "message_level": "ERROR",
                "resource_uuid": "vol-other",
                "resource_type": "VOLUME",
                "user_message": "wrong volume",
                "created_at": "2026-07-07T00:00:01Z",
            },
            {
                "id": "msg-3",
                "event_id": "event-3",
                "request_id": "req-3",
                "message_level": "ERROR",
                "resource_uuid": "vol-1",
                "resource_type": "SNAPSHOT",
                "user_message": "wrong resource type",
                "created_at": "2026-07-07T00:00:02Z",
            },
            "not-a-dict",
        ]
    )

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
    ):
        diagnostic = volume_delete_recovery.diagnose_volume_delete_issue(conn, "vol-1")

    assert len(diagnostic.messages) == 1
    message = diagnostic.messages[0]
    assert message.request_id == "req-1"
    assert message.event_id == "event-1"
    assert message.user_message == "Primary volume delete blocker"
    assert "cinder_message=Primary volume delete blocker" in diagnostic.evidence


def test_diagnose_volume_delete_issue_tolerates_message_endpoint_failure():
    conn = make_mock_conn()
    conn.block_storage.get_volume.return_value = _make_volume("error_deleting")
    conn.block_storage.get_endpoint.return_value = "http://cinder"
    exc = Exception("messages disabled")
    exc.response = SimpleNamespace(status_code=403)
    conn.session.get.side_effect = exc

    with (
        patch("app.services.volume_delete_recovery.cinder.list_snapshots", return_value=[]),
        patch("app.services.volume_delete_recovery.cinder.list_backups", return_value=[]),
    ):
        diagnostic = volume_delete_recovery.diagnose_volume_delete_issue(conn, "vol-1")

    assert diagnostic.root_cause_code == "recoverable_error_deleting"
    assert diagnostic.messages == []
    assert "cinder_messages_unavailable" in diagnostic.evidence


def test_force_delete_volume_calls_raise_for_status_when_available():
    conn = make_mock_conn()
    conn.block_storage.get_endpoint.return_value = "http://cinder"
    response = MagicMock()
    conn.session.post.return_value = response

    cinder.force_delete_volume(conn, "vol-1")

    conn.session.post.assert_called_once_with(
        "http://cinder/volumes/vol-1/action",
        json={"os-force_delete": {}},
    )
    response.raise_for_status.assert_called_once_with()
