from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from openstack.exceptions import ResourceNotFound

from app.models.storage import (
    VolumeDeleteDependency,
    VolumeDeleteDiagnostic,
    VolumeDeleteMessage,
    VolumeDeleteRecoveryResult,
    VolumeDeleteRecoveryStep,
)
from app.services import cinder

_RECOVERABLE_DELETE_STATUSES = {
    "error",
    "deleting",
    "error_deleting",
    "error_extending",
    "error_restoring",
    "error_managing",
}
_DEPENDENCY_TERMINAL_STATUSES = {"deleted"}


def _as_str(value: Any, limit: int = 200) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]


def _safe_detail(exc: Exception) -> str:
    message = str(exc)
    if message:
        return f"{type(exc).__name__}: {message[:200]}"
    return type(exc).__name__


def _volume_project_id(volume: Any) -> str | None:
    return getattr(volume, "project_id", None) or getattr(volume, "os-vol-tenant-attr:tenant_id", None)


def _volume_status(volume: Any) -> str | None:
    status = (getattr(volume, "status", None) or "").lower()
    return status or None


def _volume_attachments(volume: Any) -> list[dict]:
    attachments: list[dict] = []
    for attachment in list(getattr(volume, "attachments", []) or []):
        if isinstance(attachment, dict):
            attachments.append(dict(attachment))
        else:
            attachments.append({"raw": str(attachment)[:200]})
    return attachments


def _project_scoped_conn(
    conn: Any,
    project_id: str | None,
    project_conn_factory: Callable[[str], Any] | None,
    evidence: list[str],
) -> Any:
    if not project_id or project_conn_factory is None:
        return conn
    try:
        target_conn = project_conn_factory(project_id)
        try:
            target_conn._afterglow_project_id = project_id
        except Exception:
            pass
        return target_conn
    except Exception:
        evidence.append("project_scoped_connection_unavailable")
        return conn


def _extract_dependency(kind: str, raw: dict) -> VolumeDeleteDependency | None:
    dep_id = _as_str(raw.get("id"))
    if not dep_id:
        return None
    return VolumeDeleteDependency(
        id=dep_id,
        status=_as_str(raw.get("status")),
        name=_as_str(raw.get("name")),
        kind=kind,  # type: ignore[arg-type]
    )


def _list_dependency_blockers(conn: Any, volume_id: str, evidence: list[str]) -> list[VolumeDeleteDependency]:
    dependencies: list[VolumeDeleteDependency] = []
    try:
        snapshots = cinder.list_snapshots(conn, volume_id=volume_id, caller_project_id=None)
        for snapshot in snapshots:
            status = (snapshot.get("status") or "").lower()
            if status not in _DEPENDENCY_TERMINAL_STATUSES:
                dep = _extract_dependency("snapshot", snapshot)
                if dep:
                    dependencies.append(dep)
    except Exception:
        evidence.append("dependency_lookup_failed")

    try:
        backups = [backup for backup in cinder.list_backups(conn) if backup.get("volume_id") == volume_id]
        for backup in backups:
            status = (backup.get("status") or "").lower()
            if status not in _DEPENDENCY_TERMINAL_STATUSES:
                dep = _extract_dependency("backup", backup)
                if dep:
                    dependencies.append(dep)
    except Exception:
        if "dependency_lookup_failed" not in evidence:
            evidence.append("dependency_lookup_failed")

    return dependencies


def _response_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        try:
            return int(status_code)
        except (TypeError, ValueError):
            return None
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        try:
            return int(status_code)
        except (TypeError, ValueError):
            return None
    return None


def _list_volume_messages(conn: Any, volume_id: str, evidence: list[str]) -> list[VolumeDeleteMessage]:
    try:
        endpoint = conn.block_storage.get_endpoint()
        response = conn.session.get(
            f"{endpoint}/messages",
            params={"limit": "100", "sort": "created_at:desc"},
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        payload = response.json() if hasattr(response, "json") else response
        raw_messages = payload.get("messages", []) if isinstance(payload, dict) else []
    except Exception as exc:
        status_code = _response_status(exc)
        if status_code in {400, 403, 404} or status_code is None:
            evidence.append("cinder_messages_unavailable")
            return []
        evidence.append("cinder_messages_unavailable")
        return []

    messages: list[VolumeDeleteMessage] = []
    for message in raw_messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("resource_uuid") or "") != volume_id:
            continue
        if str(message.get("resource_type") or "").upper() != "VOLUME":
            continue
        messages.append(
            VolumeDeleteMessage(
                id=_as_str(message.get("id")),
                event_id=_as_str(message.get("event_id")),
                request_id=_as_str(message.get("request_id")),
                message_level=_as_str(message.get("message_level")),
                resource_uuid=_as_str(message.get("resource_uuid")),
                resource_type=_as_str(message.get("resource_type")),
                user_message=_as_str(message.get("user_message"), 500),
                created_at=_as_str(message.get("created_at")),
            )
        )
        if len(messages) >= 10:
            break
    return messages


def _message_evidence(messages: list[VolumeDeleteMessage]) -> list[str]:
    evidence: list[str] = []
    for message in messages[:3]:
        text = message.user_message or message.event_id or message.request_id
        if text:
            evidence.append(f"cinder_message={text[:200]}")
    return evidence


def _already_deleted_diagnostic(volume_id: str) -> VolumeDeleteDiagnostic:
    return VolumeDeleteDiagnostic(
        volume_id=volume_id,
        status=None,
        project_id=None,
        attachments=[],
        dependencies=[],
        messages=[],
        root_cause_code="already_deleted",
        confidence="high",
        summary="Cinder에서 볼륨을 찾을 수 없어 이미 삭제된 것으로 판단됩니다.",
        evidence=["volume_not_found"],
        recommended_action="목록을 새로고침하세요.",
        recovery_available=True,
        force_delete_available=False,
    )


def diagnose_volume_delete_issue(
    conn: Any,
    volume_id: str,
    project_conn_factory: Callable[[str], Any] | None = None,
) -> VolumeDeleteDiagnostic:
    try:
        volume = conn.block_storage.get_volume(volume_id)
    except ResourceNotFound:
        return _already_deleted_diagnostic(volume_id)

    status = _volume_status(volume)
    project_id = _volume_project_id(volume)
    attachments = _volume_attachments(volume)
    evidence: list[str] = []
    target_conn = _project_scoped_conn(conn, project_id, project_conn_factory, evidence)
    dependencies = _list_dependency_blockers(target_conn, volume_id, evidence)
    messages = _list_volume_messages(target_conn, volume_id, evidence)
    evidence.extend(_message_evidence(messages))

    base = {
        "volume_id": volume_id,
        "status": status,
        "project_id": project_id,
        "attachments": attachments,
        "dependencies": dependencies,
        "messages": messages,
    }

    if attachments:
        attachment_evidence: list[str] = []
        for attachment in attachments:
            server_id = attachment.get("server_id") or attachment.get("serverId") or attachment.get("instance")
            device = attachment.get("device")
            if server_id or device:
                attachment_evidence.append(f"attachment:{server_id or 'unknown'}:{device or 'unknown'}")
        return VolumeDeleteDiagnostic(
            **base,
            root_cause_code="attached_volume_delete_blocked",
            confidence="high",
            summary="볼륨이 인스턴스에 연결된 상태라 Cinder가 삭제를 거부하는 것으로 판단됩니다.",
            evidence=[f"status={status}", *attachment_evidence, *evidence],
            recommended_action="인스턴스 연결을 먼저 해제하고 실제 detach 완료를 확인한 뒤 삭제 복구를 다시 실행하세요.",
            recovery_available=False,
            force_delete_available=False,
        )

    if dependencies:
        dependency_evidence = [f"{dep.kind}:{dep.id}:{dep.status or 'unknown'}" for dep in dependencies]
        return VolumeDeleteDiagnostic(
            **base,
            root_cause_code="dependent_snapshot_or_backup",
            confidence="high",
            summary="볼륨에 연결된 스냅샷 또는 백업이 남아 있어 자동 삭제 복구를 중단했습니다.",
            evidence=[f"status={status}", *dependency_evidence, *evidence],
            recommended_action="스냅샷/백업을 보존할지 삭제할지 명시적으로 결정한 뒤 별도 작업으로 정리하고 다시 시도하세요.",
            recovery_available=False,
            force_delete_available=False,
        )

    if status in {"error_deleting", "deleting"}:
        return VolumeDeleteDiagnostic(
            **base,
            root_cause_code="recoverable_error_deleting",
            confidence="high",
            summary="연결과 종속 리소스가 없어 Cinder 상태 재설정 후 삭제/강제 삭제로 복구 가능한 상태입니다.",
            evidence=[f"status={status}", *evidence],
            recommended_action="자동 복구를 실행해 상태를 error/detached로 재설정한 뒤 일반 삭제와 강제 삭제 검증을 순차 수행하세요.",
            recovery_available=True,
            force_delete_available=True,
        )

    if status in _RECOVERABLE_DELETE_STATUSES:
        return VolumeDeleteDiagnostic(
            **base,
            root_cause_code="recoverable_error_state",
            confidence="medium",
            summary="연결과 종속 리소스가 없는 Cinder 오류 상태라 삭제 복구를 시도할 수 있습니다.",
            evidence=[f"status={status}", *evidence],
            recommended_action="자동 복구를 실행해 상태 재설정, 일반 삭제, 필요 시 강제 삭제까지 수행하세요.",
            recovery_available=True,
            force_delete_available=True,
        )

    if status == "available":
        return VolumeDeleteDiagnostic(
            **base,
            root_cause_code="normal_delete_possible",
            confidence="medium",
            summary="볼륨이 available 상태라 일반 관리자 삭제 경로를 먼저 사용해야 합니다.",
            evidence=[f"status={status}", *evidence],
            recommended_action="기존 관리자 볼륨 삭제 버튼으로 일반 삭제를 실행하세요.",
            recovery_available=False,
            force_delete_available=False,
        )

    return VolumeDeleteDiagnostic(
        **base,
        root_cause_code="not_recoverable_status",
        confidence="low",
        summary="현재 볼륨 상태는 자동 삭제 복구 대상이 아닙니다.",
        evidence=([f"status={status}"] if status else []) + evidence,
        recommended_action="Cinder 상태와 작업 로그를 수동으로 확인한 뒤 적절한 복구 절차를 선택하세요.",
        recovery_available=False,
        force_delete_available=False,
    )


def _resolve_operation_conn(
    conn: Any,
    diagnostic: VolumeDeleteDiagnostic,
    project_conn_factory: Callable[[str], Any] | None,
) -> Any:
    evidence: list[str] = []
    return _project_scoped_conn(conn, diagnostic.project_id, project_conn_factory, evidence)


def _wait_volume_absent(
    conn: Any,
    volume_id: str,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> tuple[bool, str | None]:
    deadline = time.monotonic() + max(timeout_seconds, 0)
    last_status: str | None = None
    while True:
        try:
            volume = conn.block_storage.get_volume(volume_id)
            last_status = _volume_status(volume)
        except ResourceNotFound:
            return True, None
        if time.monotonic() >= deadline:
            return False, last_status
        time.sleep(max(min(poll_interval_seconds, deadline - time.monotonic()), 0))


def recover_delete_volume(
    conn: Any,
    volume_id: str,
    project_conn_factory: Callable[[str], Any] | None = None,
    verify_timeout_seconds: int = 30,
    poll_interval_seconds: float = 2.0,
) -> VolumeDeleteRecoveryResult:
    diagnostic = diagnose_volume_delete_issue(conn, volume_id, project_conn_factory)
    steps: list[VolumeDeleteRecoveryStep] = [
        VolumeDeleteRecoveryStep(action="diagnose", status="success", detail=diagnostic.root_cause_code)
    ]

    if diagnostic.root_cause_code == "already_deleted":
        return VolumeDeleteRecoveryResult(
            volume_id=volume_id,
            status="already_deleted",
            verified_deleted=True,
            final_status=None,
            diagnostic=diagnostic,
            steps=steps,
        )

    if not diagnostic.recovery_available:
        steps.append(
            VolumeDeleteRecoveryStep(
                action="delete",
                status="skipped",
                detail=diagnostic.recommended_action,
            )
        )
        return VolumeDeleteRecoveryResult(
            volume_id=volume_id,
            status="blocked",
            verified_deleted=False,
            final_status=diagnostic.status,
            diagnostic=diagnostic,
            steps=steps,
        )

    target_conn = _resolve_operation_conn(conn, diagnostic, project_conn_factory)
    last_status = diagnostic.status

    try:
        cinder.reset_volume_status(target_conn, volume_id, "error", "detached")
        steps.append(VolumeDeleteRecoveryStep(action="reset_status", status="success", detail="error/detached"))
    except Exception as exc:
        steps.append(VolumeDeleteRecoveryStep(action="reset_status", status="failed", detail=_safe_detail(exc)))

    delete_raised = False
    try:
        cinder.delete_volume(target_conn, volume_id)
        steps.append(VolumeDeleteRecoveryStep(action="delete", status="success", detail="normal_delete_submitted"))
        verified, last_status = _wait_volume_absent(
            target_conn,
            volume_id,
            verify_timeout_seconds,
            poll_interval_seconds,
        )
        steps.append(
            VolumeDeleteRecoveryStep(
                action="verify_after_delete",
                status="success" if verified else "failed",
                detail="deleted" if verified else f"still_present:{last_status or 'unknown'}",
            )
        )
        if verified:
            return VolumeDeleteRecoveryResult(
                volume_id=volume_id,
                status="deleted",
                verified_deleted=True,
                final_status=None,
                diagnostic=diagnostic,
                steps=steps,
            )
    except Exception as exc:
        delete_raised = True
        steps.append(VolumeDeleteRecoveryStep(action="delete", status="failed", detail=_safe_detail(exc)))

    if not diagnostic.force_delete_available:
        return VolumeDeleteRecoveryResult(
            volume_id=volume_id,
            status="failed" if delete_raised else "delete_submitted",
            verified_deleted=False,
            final_status=last_status,
            diagnostic=diagnostic,
            steps=steps,
        )

    try:
        cinder.force_delete_volume(target_conn, volume_id)
        steps.append(VolumeDeleteRecoveryStep(action="force_delete", status="success", detail="force_delete_submitted"))
    except Exception as exc:
        steps.append(VolumeDeleteRecoveryStep(action="force_delete", status="failed", detail=_safe_detail(exc)))
        return VolumeDeleteRecoveryResult(
            volume_id=volume_id,
            status="failed",
            verified_deleted=False,
            final_status=last_status,
            diagnostic=diagnostic,
            steps=steps,
        )

    verified, last_status = _wait_volume_absent(
        target_conn,
        volume_id,
        verify_timeout_seconds,
        poll_interval_seconds,
    )
    steps.append(
        VolumeDeleteRecoveryStep(
            action="verify_after_force_delete",
            status="success" if verified else "failed",
            detail="deleted" if verified else f"still_present:{last_status or 'unknown'}",
        )
    )
    if verified:
        return VolumeDeleteRecoveryResult(
            volume_id=volume_id,
            status="deleted",
            verified_deleted=True,
            final_status=None,
            diagnostic=diagnostic,
            steps=steps,
        )

    return VolumeDeleteRecoveryResult(
        volume_id=volume_id,
        status="delete_submitted",
        verified_deleted=False,
        final_status=last_status,
        diagnostic=diagnostic,
        steps=steps,
    )
