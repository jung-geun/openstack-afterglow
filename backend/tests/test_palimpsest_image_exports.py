"""Palimpsest Glance image export regression test suite.

Coverage:
1. Canonical source/artifact fingerprints
2. Serializer response and safe filename
3. Enqueue validation (status/format/size/project scope)
4. Same-project complete reuse/reset and active-job conflict
5. Cross-project byte reuse only after requester Glance visibility fetch
6. Lease claim/reclaim/attempt exhaustion and owner-fenced CAS
7. Authorization logic (owner/public/community/accepted-shared vs revoked)
8. Revision and hash mismatch detection
9. Actual-byte and disk-space limits
10. Source backing/data-file recursive rejection before conversion
11. Same-driver passthrough without copy
12. VHD mapping to -O vpc
13. qemu timeout/failure/output validation
14. Symlink-safe promotion
15. Scratch directory cleanup
16. Soft delete behavior
17. One-use ticket / Range / project isolation API paths
18. Reference-aware GC in export maintenance
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.deps import get_token_info
from app.main import app
from app.models.db import PalimpsestHubLayer, PalimpsestImageExport
from app.services.palimpsest_hub_store import (
    IMAGE_FORMAT_SPECS,
    HubStoreError,
    LocalPathBlobStore,
)
from app.services.palimpsest_image_exports import (
    CONVERTER_CONTRACT,
    STATUS_COMPLETE,
    STATUS_CONVERTING,
    STATUS_DOWNLOADING,
    STATUS_ERROR,
    STATUS_QUEUED,
    ImageExportError,
    ImageExportNotFound,
    _has_external_reference,
    _remove_scratch_dir,
    _scratch_dir_for,
    _update_job_cas,
    build_qemu_img_convert_command,
    claim_next_image_export,
    compute_artifact_key,
    compute_source_fingerprint,
    enqueue_image_export,
    process_one_image_export,
    run_export_maintenance,
    serialize_export,
    soft_delete_project_export,
    validate_qemu_img_support,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _make_dummy_image(
    image_id: str = "img-123",
    name: str = "ubuntu-22.04.raw",
    disk_format: str = "raw",
    size: int = 1024 * 1024,
    status: str = "active",
    virtual_size: int | None = 1024 * 1024,
    checksum: str | None = "e10adc3949ba59abbe56e057f20f883e",
    os_hash_algo: str | None = "sha256",
    os_hash_value: str | None = "a" * 64,
    updated_at: str | None = "2026-07-31T00:00:00Z",
    owner: str | None = "test-project-123",
    visibility: str | None = "private",
) -> MagicMock:
    img = MagicMock()
    img.id = image_id
    img.name = name
    img.disk_format = disk_format
    img.size = size
    img.status = status
    img.virtual_size = virtual_size
    img.checksum = checksum
    img.os_hash_algo = os_hash_algo
    img.os_hash_value = os_hash_value
    img.updated_at = updated_at
    img.owner = owner
    img.visibility = visibility
    return img


class FakeAsyncSession:
    """Small query-aware in-memory stand-in for focused service tests."""

    def __init__(self, db_store: list[Any]):
        self.db_store = db_store
        self.added: list[Any] = []
        self._rowcount = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def begin(self):
        return self

    def add(self, item: Any):
        if not getattr(item, "id", None):
            item.id = str(uuid.uuid4())
        self.db_store.append(item)
        self.added.append(item)

    async def execute(self, statement: Any):
        stmt_str = str(statement).lower()
        params = statement.compile().params

        def param(prefix: str):
            return next((value for key, value in params.items() if key.startswith(prefix)), None)

        if "update palimpsest_image_exports" in stmt_str:
            expected_id = param("id_")
            expected_owner = param("lease_owner_")
            matched = [
                row
                for row in self.db_store
                if isinstance(row, PalimpsestImageExport)
                and (expected_id is None or row.id == expected_id)
                and (expected_owner is None or row.lease_owner == expected_owner)
                and row.deleted_at is None
            ]
            for row in matched:
                for column, expression in statement._values.items():
                    setattr(row, column.key, getattr(expression, "value", expression))
            return MagicMock(rowcount=len(matched))

        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        matching = [row for row in self.db_store if entity is None or isinstance(row, entity)]

        expected_project = param("project_id_")
        expected_artifact = param("artifact_key_")
        expected_id = param("id_")
        expected_source = param("source_image_id_")
        expected_status = param("status_")
        expected_result_digest = param("result_blob_digest_")
        expected_blob_digest = param("blob_digest_")
        if expected_result_digest is not None:
            matching = [row for row in matching if getattr(row, "result_blob_digest", None) == expected_result_digest]
        if expected_blob_digest is not None:
            matching = [row for row in matching if getattr(row, "blob_digest", None) == expected_blob_digest]
        if expected_project is not None:
            matching = [row for row in matching if getattr(row, "project_id", None) == expected_project]
        if expected_artifact is not None:
            matching = [row for row in matching if getattr(row, "artifact_key", None) == expected_artifact]
        if expected_id is not None:
            matching = [row for row in matching if getattr(row, "id", None) == expected_id]
        if expected_source is not None:
            matching = [row for row in matching if getattr(row, "source_image_id", None) == expected_source]
        expected_deleted_after = param("deleted_at_")
        if "deleted_at is null" in stmt_str and "deleted_at >" in stmt_str:
            matching = [
                row
                for row in matching
                if getattr(row, "deleted_at", None) is None
                or (expected_deleted_after is not None and getattr(row, "deleted_at", None) > expected_deleted_after)
            ]
        elif "deleted_at is null" in stmt_str:
            matching = [row for row in matching if getattr(row, "deleted_at", None) is None]
        if "status not in" in stmt_str and isinstance(expected_status, list):
            matching = [row for row in matching if getattr(row, "status", None) not in expected_status]
        elif "status =" in stmt_str and isinstance(expected_status, str):
            matching = [row for row in matching if getattr(row, "status", None) == expected_status]

        scalar_values: list[Any] = matching
        if descriptions:
            expression = descriptions[0].get("expr")
            key = getattr(expression, "key", None)
            if key and entity is not None and expression is not entity:
                scalar_values = [getattr(row, key) for row in matching]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = scalar_values[0] if scalar_values else None
        mock_result.scalar_one.return_value = scalar_values[0] if scalar_values else None
        mock_result.scalars.return_value.all.return_value = scalar_values
        mock_result.scalars.return_value.first.return_value = scalar_values[0] if scalar_values else None
        mock_result.rowcount = len(matching)
        return mock_result


class FakeSessionFactory:
    def __init__(self, db_store: list[Any] | None = None):
        self.db_store = db_store if db_store is not None else []

    def __call__(self):
        return FakeAsyncSession(self.db_store)


class RaceExitSession(FakeAsyncSession):
    """Raise a commit-time race once, replacing the losing row with the winner."""

    def __init__(self, db_store: list[Any], winner: PalimpsestImageExport, exc: Exception):
        super().__init__(db_store)
        self.winner = winner
        self.exc = exc
        self.raised = False

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.raised:
            self.raised = True
            self.db_store[:] = [self.winner]
            raise self.exc
        return None


class RaceSessionFactory(FakeSessionFactory):
    def __init__(self, winner: PalimpsestImageExport, exc: Exception):
        super().__init__([])
        self.winner = winner
        self.exc = exc
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls == 2:
            return RaceExitSession(self.db_store, self.winner, self.exc)
        return FakeAsyncSession(self.db_store)


# ---------------------------------------------------------------------------
# 1. Canonical Source/Artifact Fingerprints
# ---------------------------------------------------------------------------


def test_compute_source_fingerprint_properties():
    fp1 = compute_source_fingerprint(
        image_id="img-1",
        disk_format="raw",
        size_bytes=1000,
        virtual_size_bytes=2000,
        checksum="md5val",
        hash_algo="sha256",
        hash_value="hashval",
        updated_at="2026-07-31T00:00:00Z",
    )
    assert isinstance(fp1, str)
    assert len(fp1) == 64

    # Deterministic
    fp2 = compute_source_fingerprint(
        image_id="img-1",
        disk_format="raw",
        size_bytes=1000,
        virtual_size_bytes=2000,
        checksum="md5val",
        hash_algo="sha256",
        hash_value="hashval",
        updated_at="2026-07-31T00:00:00Z",
    )
    assert fp1 == fp2

    # Any field change alters fingerprint
    fp_diff = compute_source_fingerprint(
        image_id="img-1",
        disk_format="raw",
        size_bytes=1001,  # size changed
        virtual_size_bytes=2000,
        checksum="md5val",
        hash_algo="sha256",
        hash_value="hashval",
        updated_at="2026-07-31T00:00:00Z",
    )
    assert fp1 != fp_diff


def test_compute_artifact_key_properties():
    fp = "a" * 64
    key1 = compute_artifact_key(fp, "qcow2")
    assert isinstance(key1, str)
    assert len(key1) == 64

    # Target format change alters key
    key2 = compute_artifact_key(fp, "vmdk")
    assert key1 != key2

    # Verify contract string incorporation
    raw = json.dumps(
        {"source_fingerprint": fp, "target_disk_format": "qcow2", "converter_contract": CONVERTER_CONTRACT},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected = hashlib.sha256(raw).hexdigest()
    assert key1 == expected


# ---------------------------------------------------------------------------
# 2. Serializer Response and Safe Filename
# ---------------------------------------------------------------------------


def test_serialize_export_complete_and_pending():
    row_pending = PalimpsestImageExport(
        id="f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
        project_id="proj-1",
        source_image_id="f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
        source_name="ubuntu.raw",
        source_disk_format="raw",
        source_size_bytes=1024,
        target_disk_format="qcow2",
        artifact_key="1234567890abcdef" * 4,
        status=STATUS_QUEUED,
        progress_pct=0,
        created_at=_now(),
    )
    data_pending = serialize_export(row_pending)
    assert data_pending["status"] == STATUS_QUEUED
    assert data_pending["filename"] is None
    assert data_pending["download_path"] is None

    row_complete = PalimpsestImageExport(
        id="f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
        project_id="proj-1",
        source_image_id="f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
        source_name="ubuntu.raw",
        source_disk_format="raw",
        source_size_bytes=1024,
        target_disk_format="qcow2",
        artifact_key="1234567890abcdef" * 4,
        result_blob_digest="sha256:" + "b" * 64,
        result_size_bytes=2048,
        status=STATUS_COMPLETE,
        progress_pct=100,
        created_at=_now(),
        completed_at=_now(),
        deleted_at=None,
    )
    data_complete = serialize_export(row_complete)
    assert data_complete["status"] == STATUS_COMPLETE
    assert data_complete["filename"] == "palimpsest-f81d4fae7dec-1234567890ab.qcow2"
    assert (
        data_complete["download_path"]
        == "/api/v1/palimpsest/hub/image-exports/f81d4fae-7dec-11d0-a765-00a0c91e6bf6/blob"
    )
    assert data_complete["blob_digest"] == "sha256:" + "b" * 64
    assert data_complete["size_bytes"] == 2048


# ---------------------------------------------------------------------------
# 3. Enqueue Validation (Status/Format/Size/Project Scope)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_image_export_validation_errors():
    conn = MagicMock()
    token_info = {"project_id": "proj-1", "user_id": "user-1"}

    # Invalid target format
    with pytest.raises(ImageExportError) as exc_info:
        await enqueue_image_export(conn, token_info, "img-1", "invalid_fmt")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "invalid_target_format"

    # Glance image not found
    with patch("app.services.palimpsest_image_exports.get_image", side_effect=Exception("not found")):
        with pytest.raises(ImageExportNotFound):
            await enqueue_image_export(conn, token_info, "img-missing", "qcow2")

    # Inactive Glance image
    dummy_inactive = _make_dummy_image(status="queued")
    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy_inactive):
        with pytest.raises(ImageExportError) as exc_info:
            await enqueue_image_export(conn, token_info, "img-1", "qcow2")
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "image_not_active"

    # Unsupported source format
    dummy_bad_src = _make_dummy_image(disk_format="iso")
    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy_bad_src):
        with pytest.raises(ImageExportError) as exc_info:
            await enqueue_image_export(conn, token_info, "img-1", "qcow2")
        assert exc_info.value.status_code == 422
        assert exc_info.value.code == "unsupported_source_format"

    # Zero size image
    dummy_zero_size = _make_dummy_image(size=0)
    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy_zero_size):
        with pytest.raises(ImageExportError) as exc_info:
            await enqueue_image_export(conn, token_info, "img-1", "qcow2")
        assert exc_info.value.status_code == 422
        assert exc_info.value.code == "invalid_image_size"

    # Oversized image
    dummy_oversized = _make_dummy_image(size=100 * 1024 * 1024 * 1024)
    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy_oversized):
        with patch("app.services.palimpsest_image_exports.get_settings") as mock_settings:
            mock_settings.return_value.palimpsest_hub_max_blob_bytes = 10 * 1024 * 1024 * 1024
            with pytest.raises(ImageExportError) as exc_info:
                await enqueue_image_export(conn, token_info, "img-1", "qcow2")
            assert exc_info.value.status_code == 413
            assert exc_info.value.code == "image_too_large"

    # Missing project scope
    dummy = _make_dummy_image()
    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with pytest.raises(ImageExportError) as exc_info:
            await enqueue_image_export(conn, {}, "img-1", "qcow2")
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "project_scope_required"


# ---------------------------------------------------------------------------
# 4. Same-Project Complete Reuse/Reset and Active-Job Conflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_same_project_active_job_conflict():
    conn = MagicMock()
    token_info = {"project_id": "proj-1"}
    dummy = _make_dummy_image()

    active_job = PalimpsestImageExport(
        id="job-active",
        project_id="proj-1",
        source_image_id="img-other",
        source_name="ubuntu.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="vmdk",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_DOWNLOADING,
        created_at=_now(),
    )

    db_store = [active_job]

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory(db_store)
        ):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = False
                with pytest.raises(ImageExportError) as exc_info:
                    await enqueue_image_export(conn, token_info, "img-1", "qcow2")
                assert exc_info.value.status_code == 409
                assert exc_info.value.code == "active_export_exists"


@pytest.mark.asyncio
async def test_enqueue_same_project_complete_reuse():
    conn = MagicMock()
    token_info = {"project_id": "proj-1"}
    dummy = _make_dummy_image(owner="proj-1")

    src_fp = compute_source_fingerprint(
        dummy.id,
        dummy.disk_format,
        dummy.size,
        dummy.virtual_size,
        dummy.checksum,
        dummy.os_hash_algo,
        dummy.os_hash_value,
        dummy.updated_at,
    )
    art_key = compute_artifact_key(src_fp, "qcow2")

    existing_complete = PalimpsestImageExport(
        id="job-complete",
        project_id="proj-1",
        source_image_id=dummy.id,
        source_name=dummy.name,
        source_disk_format=dummy.disk_format,
        source_size_bytes=dummy.size,
        target_disk_format="qcow2",
        source_fingerprint=src_fp,
        artifact_key=art_key,
        result_blob_digest="sha256:" + "d" * 64,
        result_size_bytes=200,
        status=STATUS_COMPLETE,
        created_at=_now(),
        deleted_at=None,
    )

    db_store = [existing_complete]

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory(db_store)
        ):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = True
                res = await enqueue_image_export(conn, token_info, dummy.id, "qcow2")
                assert res.id == "job-complete"
                assert res.status == STATUS_COMPLETE


@pytest.mark.asyncio
async def test_enqueue_same_project_resets_error_job():
    conn = MagicMock()
    token_info = {"project_id": "proj-1"}
    dummy = _make_dummy_image()

    src_fp = compute_source_fingerprint(
        dummy.id,
        dummy.disk_format,
        dummy.size,
        dummy.virtual_size,
        dummy.checksum,
        dummy.os_hash_algo,
        dummy.os_hash_value,
        dummy.updated_at,
    )
    art_key = compute_artifact_key(src_fp, "qcow2")

    failed_job = PalimpsestImageExport(
        id="job-failed",
        project_id="proj-1",
        source_image_id=dummy.id,
        source_name=dummy.name,
        source_disk_format=dummy.disk_format,
        source_size_bytes=dummy.size,
        target_disk_format="qcow2",
        source_fingerprint=src_fp,
        artifact_key=art_key,
        status=STATUS_ERROR,
        error_code="conversion_failed",
        error_message="failed prior",
        created_at=_now(),
    )

    db_store = [failed_job]

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory(db_store)
        ):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = False
                res = await enqueue_image_export(conn, token_info, dummy.id, "qcow2")
                assert res.id == "job-failed"
                assert res.status == STATUS_QUEUED
                assert res.error_code is None
                assert res.error_message is None


@pytest.mark.asyncio
async def test_enqueue_integrity_race_preserves_claimed_winner_lease():
    conn = MagicMock()
    token_info = {"project_id": "proj-1"}
    dummy = _make_dummy_image(owner="proj-1")
    src_fp = compute_source_fingerprint(
        dummy.id,
        dummy.disk_format,
        dummy.size,
        dummy.virtual_size,
        dummy.checksum,
        dummy.os_hash_algo,
        dummy.os_hash_value,
        dummy.updated_at,
    )
    winner = PalimpsestImageExport(
        id="job-race-winner",
        project_id="proj-1",
        source_image_id=dummy.id,
        source_name=dummy.name,
        source_disk_format=dummy.disk_format,
        source_size_bytes=dummy.size,
        target_disk_format="qcow2",
        source_fingerprint=src_fp,
        artifact_key=compute_artifact_key(src_fp, "qcow2"),
        status=STATUS_DOWNLOADING,
        progress_pct=10,
        attempts=1,
        lease_owner="worker-winner",
        lease_expires_at=_now() + timedelta(minutes=1),
        started_at=_now(),
        created_at=_now(),
    )
    factory = RaceSessionFactory(winner, IntegrityError("INSERT", {}, Exception("duplicate")))

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with patch("app.services.palimpsest_image_exports.get_session_factory", return_value=factory):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = False
                result = await enqueue_image_export(conn, token_info, dummy.id, "qcow2")

    assert result is winner
    assert winner.status == STATUS_DOWNLOADING
    assert winner.attempts == 1
    assert winner.lease_owner == "worker-winner"
    assert winner.started_at is not None


@pytest.mark.asyncio
async def test_enqueue_retries_database_deadlock_and_observes_project_winner():
    conn = MagicMock()
    token_info = {"project_id": "proj-1"}
    dummy = _make_dummy_image(owner="proj-1")
    winner = PalimpsestImageExport(
        id="job-deadlock-winner",
        project_id="proj-1",
        source_image_id="another-image",
        source_name="another.raw",
        source_disk_format="raw",
        source_size_bytes=1024,
        target_disk_format="vmdk",
        source_fingerprint="d" * 64,
        artifact_key="e" * 64,
        status=STATUS_DOWNLOADING,
        progress_pct=10,
        attempts=1,
        lease_owner="worker-winner",
        lease_expires_at=_now() + timedelta(minutes=1),
        created_at=_now(),
    )
    deadlock = OperationalError("INSERT", {}, Exception(1213, "Deadlock found"))
    factory = RaceSessionFactory(winner, deadlock)

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with patch("app.services.palimpsest_image_exports.get_session_factory", return_value=factory):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = False
                with pytest.raises(ImageExportError) as exc_info:
                    await enqueue_image_export(conn, token_info, dummy.id, "qcow2")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "active_export_exists"
    assert winner.lease_owner == "worker-winner"
    assert factory.calls == 3


# ---------------------------------------------------------------------------
# 5. Cross-Project Byte Reuse (Requires Requester Glance Visibility)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_cross_project_byte_reuse():
    requester_conn = MagicMock()
    token_info = {"project_id": "proj-requester"}
    dummy = _make_dummy_image(owner="proj-owner", visibility="public")

    src_fp = compute_source_fingerprint(
        dummy.id,
        dummy.disk_format,
        dummy.size,
        dummy.virtual_size,
        dummy.checksum,
        dummy.os_hash_algo,
        dummy.os_hash_value,
        dummy.updated_at,
    )
    art_key = compute_artifact_key(src_fp, "qcow2")

    global_export = PalimpsestImageExport(
        id="job-owner",
        project_id="proj-owner",
        source_image_id=dummy.id,
        source_name=dummy.name,
        source_disk_format=dummy.disk_format,
        source_size_bytes=dummy.size,
        target_disk_format="qcow2",
        source_fingerprint=src_fp,
        artifact_key=art_key,
        result_blob_digest="sha256:" + "e" * 64,
        result_size_bytes=500,
        status=STATUS_COMPLETE,
        created_at=_now(),
        deleted_at=None,
    )

    db_store = [global_export]

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy) as mock_get_image:
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory(db_store)
        ):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = True
                mock_blob_store.return_value.size.return_value = 500

                res = await enqueue_image_export(requester_conn, token_info, dummy.id, "qcow2")
                # Must verify Glance access with requester's conn first
                mock_get_image.assert_called_with(requester_conn, dummy.id)
                assert res.project_id == "proj-requester"
                assert res.status == STATUS_COMPLETE
                assert res.result_blob_digest == "sha256:" + "e" * 64


@pytest.mark.asyncio
async def test_enqueue_shared_image_reuses_after_requester_visibility_succeeds():
    requester_conn = MagicMock()
    token_info = {"project_id": "proj-requester"}
    dummy = _make_dummy_image(owner="proj-owner", visibility="shared")
    src_fp = compute_source_fingerprint(
        dummy.id,
        dummy.disk_format,
        dummy.size,
        dummy.virtual_size,
        dummy.checksum,
        dummy.os_hash_algo,
        dummy.os_hash_value,
        dummy.updated_at,
    )
    art_key = compute_artifact_key(src_fp, "qcow2")
    global_export = PalimpsestImageExport(
        id="job-owner-shared",
        project_id="proj-owner",
        source_image_id=dummy.id,
        source_name=dummy.name,
        source_disk_format=dummy.disk_format,
        source_size_bytes=dummy.size,
        target_disk_format="qcow2",
        source_fingerprint=src_fp,
        artifact_key=art_key,
        result_blob_digest="sha256:" + "e" * 64,
        result_size_bytes=500,
        status=STATUS_COMPLETE,
        created_at=_now(),
    )
    db_store = [global_export]

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy) as mock_get_image:
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory",
            return_value=FakeSessionFactory(db_store),
        ):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = True
                mock_blob_store.return_value.size.return_value = 500
                result = await enqueue_image_export(requester_conn, token_info, dummy.id, "qcow2")

    mock_get_image.assert_called_once_with(requester_conn, dummy.id)
    assert result.project_id == "proj-requester"
    assert result.status == STATUS_COMPLETE
    assert result.result_blob_digest == "sha256:" + "e" * 64
    assert len(db_store) == 2


@pytest.mark.asyncio
async def test_enqueue_shared_image_reuses_same_project_completed_export():
    requester_conn = MagicMock()
    token_info = {"project_id": "proj-requester"}
    dummy = _make_dummy_image(owner="proj-owner", visibility="shared")
    src_fp = compute_source_fingerprint(
        dummy.id,
        dummy.disk_format,
        dummy.size,
        dummy.virtual_size,
        dummy.checksum,
        dummy.os_hash_algo,
        dummy.os_hash_value,
        dummy.updated_at,
    )
    completed = PalimpsestImageExport(
        id="job-requester-shared",
        project_id="proj-requester",
        source_image_id=dummy.id,
        source_name=dummy.name,
        source_disk_format=dummy.disk_format,
        source_size_bytes=dummy.size,
        target_disk_format="qcow2",
        source_fingerprint=src_fp,
        artifact_key=compute_artifact_key(src_fp, "qcow2"),
        result_blob_digest="sha256:" + "c" * 64,
        result_size_bytes=500,
        status=STATUS_COMPLETE,
        progress_pct=100,
        created_at=_now(),
    )
    db_store = [completed]

    with patch("app.services.palimpsest_image_exports.get_image", return_value=dummy):
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory",
            return_value=FakeSessionFactory(db_store),
        ):
            with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_blob_store:
                mock_blob_store.return_value.exists.return_value = True
                result = await enqueue_image_export(requester_conn, token_info, dummy.id, "qcow2")

    assert result is completed
    assert result.status == STATUS_COMPLETE
    assert result.result_blob_digest == "sha256:" + "c" * 64


# ---------------------------------------------------------------------------
# 6. Lease Claim / Reclaim / Attempt Exhaustion and Owner-Fenced CAS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_next_image_export_due_and_attempt_exhaustion():
    now = _now()

    due_job = PalimpsestImageExport(
        id="job-due",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="qcow2",
        source_fingerprint="a" * 64,
        artifact_key="b" * 64,
        status=STATUS_QUEUED,
        attempts=0,
        next_at=now - timedelta(seconds=10),
        created_at=now,
    )

    exhausted_job = PalimpsestImageExport(
        id="job-exhausted",
        project_id="proj-1",
        source_image_id="img-2",
        source_name="img2.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="qcow2",
        source_fingerprint="a" * 64,
        artifact_key="c" * 64,
        status=STATUS_QUEUED,
        attempts=3,  # 4th claim attempt triggers exhaustion
        next_at=now - timedelta(seconds=10),
        created_at=now,
    )

    # Claim due job
    with patch("app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory([due_job])):
        claimed = await claim_next_image_export(owner="worker-1")
        assert claimed is not None
        assert claimed.id == "job-due"
        assert claimed.lease_owner == "worker-1"
        assert claimed.status == STATUS_DOWNLOADING
        assert claimed.attempts == 1

    # Claim exhausted job
    with patch(
        "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory([exhausted_job])
    ):
        claimed = await claim_next_image_export(owner="worker-1")
        assert claimed is None
        assert exhausted_job.status == STATUS_ERROR
        assert exhausted_job.error_code == "attempts_exhausted"


@pytest.mark.asyncio
async def test_update_job_cas_owner_fenced():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))

    ok = await _update_job_cas(mock_session, "job-1", owner="worker-1", status=STATUS_CONVERTING)
    assert ok is True

    mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    ok_failed = await _update_job_cas(mock_session, "job-1", owner="worker-wrong", status=STATUS_CONVERTING)
    assert ok_failed is False


# ---------------------------------------------------------------------------
# 7. Authorization Logic (Owner / Public / Community / Accepted-Shared vs Revoked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_one_image_export_authorization():
    job = PalimpsestImageExport(
        id="job-auth",
        project_id="proj-req",
        source_image_id="img-auth",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=1024,
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_QUEUED,
        lease_owner="worker-1",
        attempts=0,
        next_at=_now() - timedelta(seconds=5),
        created_at=_now(),
    )

    # 1. Shared visibility but member not accepted (revoked / unauthorized)
    img_shared_unaccepted = _make_dummy_image(
        image_id="img-auth",
        owner="proj-other",
        visibility="shared",
    )
    member_pending = MagicMock(member_id="proj-req", status="pending")

    admin_conn = MagicMock()
    admin_conn.image.members.return_value = [member_pending]

    db_store = [job]

    with patch("app.services.palimpsest_image_exports.claim_next_image_export", return_value=job):
        with patch("app.services.palimpsest_image_exports.get_admin_connection_for_project", return_value=admin_conn):
            with patch("app.services.palimpsest_image_exports.get_image", return_value=img_shared_unaccepted):
                with patch(
                    "app.services.palimpsest_image_exports.get_session_factory",
                    return_value=FakeSessionFactory(db_store),
                ):
                    with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_bs:
                        mock_bs.return_value.exports_dir = Path("/tmp/hub/exports")
                        processed = await process_one_image_export(owner="worker-1")
                        assert processed is True
                        assert job.status == STATUS_ERROR
                        assert job.error_code == "access_denied"


# ---------------------------------------------------------------------------
# 8. Revision and Hash Mismatch Detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_one_image_export_revision_mismatch():
    job = PalimpsestImageExport(
        id="job-rev",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=1024,
        source_virtual_size_bytes=1024,
        source_checksum="md5",
        source_hash_algo="sha256",
        source_hash_value="a" * 64,
        source_updated_at="2026-07-31T00:00:00Z",
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_QUEUED,
        lease_owner="worker-1",
        attempts=0,
        next_at=_now() - timedelta(seconds=5),
        created_at=_now(),
    )

    # Image metadata modified (size changed to 2048)
    img_modified = _make_dummy_image(
        image_id="img-1",
        size=2048,
        owner="proj-1",
        visibility="private",
    )

    admin_conn = MagicMock()

    with patch("app.services.palimpsest_image_exports.claim_next_image_export", return_value=job):
        with patch("app.services.palimpsest_image_exports.get_admin_connection_for_project", return_value=admin_conn):
            with patch("app.services.palimpsest_image_exports.get_image", return_value=img_modified):
                with patch(
                    "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory([job])
                ):
                    with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_bs:
                        mock_bs.return_value.exports_dir = Path("/tmp/hub/exports")
                        processed = await process_one_image_export(owner="worker-1")
                        assert processed is True
                        assert job.status == STATUS_ERROR
                        assert job.error_code == "source_image_modified"


# ---------------------------------------------------------------------------
# 9. Actual-Byte and Disk-Space Limits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_one_image_export_insufficient_disk_space():
    job = PalimpsestImageExport(
        id="job-space",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=10 * 1024 * 1024 * 1024,
        source_virtual_size_bytes=10 * 1024 * 1024 * 1024,
        source_checksum="md5",
        source_hash_algo="sha256",
        source_hash_value="a" * 64,
        source_updated_at="2026-07-31T00:00:00Z",
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_QUEUED,
        lease_owner="worker-1",
        attempts=0,
        next_at=_now() - timedelta(seconds=5),
        created_at=_now(),
    )

    img = _make_dummy_image(
        image_id="img-1",
        size=10 * 1024 * 1024 * 1024,
        virtual_size=10 * 1024 * 1024 * 1024,
        checksum="md5",
        os_hash_algo="sha256",
        os_hash_value="a" * 64,
        updated_at="2026-07-31T00:00:00Z",
        owner="proj-1",
    )

    admin_conn = MagicMock()

    with patch("app.services.palimpsest_image_exports.claim_next_image_export", return_value=job):
        with patch("app.services.palimpsest_image_exports.get_admin_connection_for_project", return_value=admin_conn):
            with patch("app.services.palimpsest_image_exports.get_image", return_value=img):
                with patch(
                    "app.services.palimpsest_image_exports.shutil.disk_usage",
                    return_value=MagicMock(free=100),
                ):  # 100 bytes free
                    with patch(
                        "app.services.palimpsest_image_exports.get_session_factory",
                        return_value=FakeSessionFactory([job]),
                    ):
                        with patch("app.services.palimpsest_image_exports.get_blob_store") as mock_bs:
                            mock_bs.return_value.exports_dir = Path("/tmp/hub/exports")
                            processed = await process_one_image_export(owner="worker-1")
                            assert processed is True
                            assert job.status == STATUS_ERROR
                            assert job.error_code == "insufficient_disk_space"
                            assert job.error_message == "Insufficient storage capacity for image export"


def _make_pipeline_job(payload: bytes) -> PalimpsestImageExport:
    return PalimpsestImageExport(
        id=f"job-pipeline-{uuid.uuid4().hex}",
        project_id="proj-1",
        source_image_id="img-pipeline",
        source_name="pipeline.raw",
        source_disk_format="raw",
        source_size_bytes=len(payload),
        source_virtual_size_bytes=len(payload),
        source_checksum=hashlib.md5(payload).hexdigest(),  # noqa: S324 — Glance compatibility
        source_hash_algo="sha256",
        source_hash_value=hashlib.sha256(payload).hexdigest(),
        source_updated_at="2026-07-31T00:00:00Z",
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="a" * 64,
        status=STATUS_DOWNLOADING,
        progress_pct=10,
        attempts=1,
        lease_owner="worker-1",
        lease_expires_at=_now() + timedelta(minutes=2),
        created_at=_now(),
    )


async def _run_pipeline_failure(
    tmp_path: Path,
    *,
    subprocess_effects: list[Any],
    mutate_digest: bool = False,
) -> tuple[PalimpsestImageExport, AsyncMock]:
    payload = b"verified source image bytes"
    job = _make_pipeline_job(payload)
    if mutate_digest:
        job.source_hash_value = "0" * 64
    image = _make_dummy_image(
        image_id=job.source_image_id,
        name=job.source_name,
        disk_format=job.source_disk_format,
        size=job.source_size_bytes,
        virtual_size=job.source_virtual_size_bytes,
        checksum=job.source_checksum,
        os_hash_algo=job.source_hash_algo,
        os_hash_value=job.source_hash_value,
        updated_at=job.source_updated_at,
        owner=job.project_id,
    )
    response = MagicMock()
    response.iter_content.return_value = [payload]
    admin_conn = MagicMock()
    admin_conn.image.download_image.return_value = response
    store = LocalPathBlobStore(tmp_path / "hub")
    subprocess_mock = AsyncMock(side_effect=subprocess_effects)
    settings = MagicMock(palimpsest_hub_max_blob_bytes=1024 * 1024 * 1024)

    with patch("app.services.palimpsest_image_exports.claim_next_image_export", return_value=job):
        with patch(
            "app.services.palimpsest_image_exports.get_admin_connection_for_project",
            return_value=admin_conn,
        ):
            with patch("app.services.palimpsest_image_exports.get_image", return_value=image):
                with patch(
                    "app.services.palimpsest_image_exports.get_session_factory",
                    return_value=FakeSessionFactory([job]),
                ):
                    with patch("app.services.palimpsest_image_exports.get_blob_store", return_value=store):
                        with patch("app.services.palimpsest_image_exports.get_settings", return_value=settings):
                            with patch(
                                "app.services.palimpsest_image_exports.shutil.disk_usage",
                                return_value=MagicMock(free=100 * 1024 * 1024 * 1024),
                            ):
                                with patch(
                                    "app.services.palimpsest_image_exports._run_subprocess",
                                    subprocess_mock,
                                ):
                                    await process_one_image_export(owner="worker-1")

    return job, subprocess_mock


@pytest.mark.asyncio
async def test_process_rejects_download_checksum_mismatch_before_qemu(tmp_path: Path):
    job, subprocess_mock = await _run_pipeline_failure(
        tmp_path,
        subprocess_effects=[],
        mutate_digest=True,
    )

    assert job.status == STATUS_ERROR
    assert job.error_code == "checksum_mismatch"
    assert job.error_message == "Downloaded image sha256 digest mismatch"
    subprocess_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_rejects_source_backing_file_before_conversion(tmp_path: Path):
    source_info = json.dumps(
        {
            "format": "raw",
            "virtual-size": len(b"verified source image bytes"),
            "backing-filename": "/private/parent.qcow2",
        }
    )
    job, subprocess_mock = await _run_pipeline_failure(
        tmp_path,
        subprocess_effects=[(0, source_info, "")],
    )

    assert job.status == STATUS_ERROR
    assert job.error_code == "unsafe_backing_file"
    assert job.error_message == "Source image contains a prohibited external file reference"
    assert "/private" not in job.error_message
    assert subprocess_mock.await_count == 1


@pytest.mark.asyncio
async def test_process_sanitizes_qemu_conversion_failure(tmp_path: Path):
    source_info = json.dumps({"format": "raw", "virtual-size": len(b"verified source image bytes")})
    measure = json.dumps({"required": len(b"verified source image bytes")})
    job, subprocess_mock = await _run_pipeline_failure(
        tmp_path,
        subprocess_effects=[
            (0, source_info, ""),
            (0, measure, ""),
            (1, "", "failed opening /private/tenant/image.raw"),
        ],
    )

    assert job.status == STATUS_ERROR
    assert job.error_code == "conversion_failed"
    assert job.error_message == "Image conversion failed"
    assert "/private" not in job.error_message
    assert subprocess_mock.await_count == 3


@pytest.mark.asyncio
async def test_process_handles_qemu_inspection_and_conversion_timeouts(tmp_path: Path):
    inspection_job, _ = await _run_pipeline_failure(
        tmp_path / "inspection",
        subprocess_effects=[TimeoutError()],
    )
    assert inspection_job.status == STATUS_ERROR
    assert inspection_job.error_code == "inspection_timeout"
    assert inspection_job.error_message == "Source image inspection timed out"

    source_info = json.dumps({"format": "raw", "virtual-size": len(b"verified source image bytes")})
    measure = json.dumps({"required": len(b"verified source image bytes")})
    conversion_job, subprocess_mock = await _run_pipeline_failure(
        tmp_path / "conversion",
        subprocess_effects=[(0, source_info, ""), (0, measure, ""), TimeoutError()],
    )
    assert conversion_job.status == STATUS_ERROR
    assert conversion_job.error_code == "conversion_timeout"
    assert conversion_job.error_message == "qemu-img convert operation timed out after 3600 seconds"
    assert subprocess_mock.await_count == 3


# ---------------------------------------------------------------------------
# 10. Source Backing/Data-File Recursive Rejection Before Conversion
# ---------------------------------------------------------------------------


def test_has_external_reference():
    assert _has_external_reference({"backing-filename": "/etc/passwd"}) is True
    assert _has_external_reference({"full-backing-filename": "/tmp/parent.qcow2"}) is True
    assert _has_external_reference({"data-file": "/var/lib/data"}) is True
    assert _has_external_reference({"info": [{"data-file": "x"}]}) is True
    assert _has_external_reference({"format": "qcow2", "virtual-size": 100}) is False


# ---------------------------------------------------------------------------
# 11. Same-Driver Passthrough Without Copy
# ---------------------------------------------------------------------------


def test_same_driver_passthrough_logic():
    src_spec = IMAGE_FORMAT_SPECS["qcow2"]
    tgt_spec = IMAGE_FORMAT_SPECS["qcow2"]
    assert src_spec.qemu_driver == tgt_spec.qemu_driver == "qcow2"


# ---------------------------------------------------------------------------
# 12. VHD Maps to -O vpc
# ---------------------------------------------------------------------------


def test_build_qemu_img_convert_command_vhd_maps_to_vpc():
    vhd_spec = IMAGE_FORMAT_SPECS["vhd"]
    assert vhd_spec.qemu_driver == "vpc"

    source = Path("/tmp/source.raw")
    target = Path("/tmp/target.vhd")
    cmd = build_qemu_img_convert_command(source, target, "raw", "vhd")
    assert cmd == ["qemu-img", "convert", "-f", "raw", "-O", "vpc", "/tmp/source.raw", "/tmp/target.vhd"]


# ---------------------------------------------------------------------------
# 13. qemu Timeout/Failure/Output Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_qemu_img_support():
    # Success case: help output lists all required drivers
    help_output = "Supported formats: raw qcow2 vmdk vdi vpc vhdx"
    proc_ok = AsyncMock()
    proc_ok.communicate.return_value = (help_output.encode(), b"")
    proc_ok.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc_ok):
        await validate_qemu_img_support()  # Should pass without error

    # Missing driver case
    help_missing = "Supported formats: raw qcow2"
    proc_missing = AsyncMock()
    proc_missing.communicate.return_value = (help_missing.encode(), b"")
    proc_missing.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=proc_missing):
        with pytest.raises(RuntimeError, match="qemu-img does not advertise required formats"):
            await validate_qemu_img_support()


# ---------------------------------------------------------------------------
# 14. Symlink-Safe Promotion
# ---------------------------------------------------------------------------


def test_promote_file_symlink_and_traversal_safety(tmp_path: Path):
    hub_root = tmp_path / "hub"
    store = LocalPathBlobStore(hub_root)
    scratch_dir = store.exports_dir / "job-1"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Symlink rejection
    target_file = scratch_dir / "target.qcow2"
    target_file.write_bytes(b"data")
    symlink_file = scratch_dir / "link.qcow2"
    symlink_file.symlink_to(target_file)

    with pytest.raises(HubStoreError, match="일반 파일이어야 합니다"):
        store.promote_file(symlink_file, max_bytes=10000)

    # Outside root rejection
    outside_file = tmp_path / "outside.qcow2"
    outside_file.write_bytes(b"data")
    with pytest.raises(HubStoreError, match="허브 루트 안의"):
        store.promote_file(outside_file, max_bytes=10000)

    # Oversized rejection
    large_file = scratch_dir / "large.qcow2"
    large_file.write_bytes(b"x" * 200)
    with pytest.raises(HubStoreError, match="허용 크기를 초과합니다"):
        store.promote_file(large_file, max_bytes=100)

    # Successful atomic promotion
    valid_file = scratch_dir / "valid.qcow2"
    valid_bytes = b"hello world palimpsest"
    valid_file.write_bytes(valid_bytes)

    promoted = store.promote_file(valid_file, max_bytes=10000)
    assert promoted.size_bytes == len(valid_bytes)
    assert promoted.blob_digest == "sha256:" + hashlib.sha256(valid_bytes).hexdigest()
    assert store.blob_path(promoted.blob_digest).is_file()


def test_promote_file_refreshes_existing_blob_gc_age(tmp_path: Path):
    store = LocalPathBlobStore(tmp_path / "hub")
    first_scratch = store.exports_dir / "first"
    first_scratch.mkdir(parents=True)
    payload = b"deduplicated export"
    first = first_scratch / "image.raw"
    first.write_bytes(payload)
    promoted = store.promote_file(first, max_bytes=1000)
    target = store.blob_path(promoted.blob_digest)
    old_time = target.stat().st_mtime - 172800
    os.utime(target, (old_time, old_time))

    second_scratch = store.exports_dir / "second"
    second_scratch.mkdir()
    duplicate = second_scratch / "image.raw"
    duplicate.write_bytes(payload)
    store.promote_file(duplicate, max_bytes=1000)

    assert target.stat().st_mtime > old_time
    assert not duplicate.exists()


# ---------------------------------------------------------------------------
# 15. Scratch Cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scratch_cleanup_in_process_one_image_export(tmp_path: Path):
    job = PalimpsestImageExport(
        id="job-scratch-test",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=10,
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_QUEUED,
        attempts=0,
        next_at=_now() - timedelta(seconds=5),
        created_at=_now(),
    )

    img = _make_dummy_image(
        image_id="img-1",
        size=10,
        virtual_size=None,
        checksum=None,
        os_hash_algo=None,
        os_hash_value=None,
        updated_at=None,
        owner="proj-1",
    )
    admin_conn = MagicMock()

    hub_root = tmp_path / "hub"
    store = LocalPathBlobStore(hub_root)
    scratch_dir = _scratch_dir_for(store.exports_dir, job, "worker-1")

    with patch("app.services.palimpsest_image_exports.claim_next_image_export", return_value=job):
        with patch("app.services.palimpsest_image_exports.get_admin_connection_for_project", return_value=admin_conn):
            with patch("app.services.palimpsest_image_exports.get_image", return_value=img):
                with patch(
                    "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory([job])
                ):
                    with patch("app.services.palimpsest_image_exports.get_blob_store", return_value=store):
                        await process_one_image_export(owner="worker-1")
                        admin_conn.image.download_image.assert_called_once_with("img-1", stream=True)
                        # Scratch directory must be cleaned up after execution
                        assert not scratch_dir.exists()


def test_lost_lease_cleanup_cannot_remove_reclaimer_scratch(tmp_path: Path):
    job = PalimpsestImageExport(
        id="job-reclaimed",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=10,
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_DOWNLOADING,
        attempts=1,
        created_at=_now(),
    )
    exports_dir = tmp_path / "exports"
    stale_path = _scratch_dir_for(exports_dir, job, "worker-stale")
    reclaimed_path = _scratch_dir_for(exports_dir, job, "worker-reclaimer")
    stale_path.mkdir(parents=True)
    reclaimed_path.mkdir()
    (reclaimed_path / "source.raw").write_bytes(b"active")

    _remove_scratch_dir(stale_path)

    assert stale_path != reclaimed_path
    assert not stale_path.exists()
    assert (reclaimed_path / "source.raw").read_bytes() == b"active"


# ---------------------------------------------------------------------------
# 16. Soft Delete Behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_project_export():
    completed_job = PalimpsestImageExport(
        id="job-complete",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k" * 64,
        status=STATUS_COMPLETE,
        created_at=_now(),
        deleted_at=None,
    )

    active_job = PalimpsestImageExport(
        id="job-active",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="qcow2",
        source_fingerprint="f" * 64,
        artifact_key="k2" * 32,
        status=STATUS_CONVERTING,
        created_at=_now(),
        deleted_at=None,
    )

    queued_job = PalimpsestImageExport(
        id="job-queued",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="vmdk",
        source_fingerprint="f" * 64,
        artifact_key="k3" * 32,
        status=STATUS_QUEUED,
        lease_owner=None,
        lease_expires_at=None,
        created_at=_now(),
        deleted_at=None,
    )

    claimed_job = PalimpsestImageExport(
        id="job-claimed",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=100,
        target_disk_format="vdi",
        source_fingerprint="f" * 64,
        artifact_key="k4" * 32,
        status=STATUS_DOWNLOADING,
        lease_owner="worker-live",
        lease_expires_at=_now() + timedelta(minutes=1),
        created_at=_now(),
        deleted_at=None,
    )

    db_store = [completed_job, active_job, queued_job, claimed_job]

    with patch("app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory(db_store)):
        # Cannot delete a live claimed job.
        with pytest.raises(ImageExportError) as exc_info:
            await soft_delete_project_export("proj-1", "job-claimed")
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "cannot_delete_active_job"

        # A queued job without a lease can be cancelled, preventing a stuck
        # queue item from locking the project's one-active-export invariant.
        cancelled = await soft_delete_project_export("proj-1", "job-queued")
        assert cancelled.deleted_at is not None

        # Soft delete completed job
        deleted = await soft_delete_project_export("proj-1", "job-complete")
        assert deleted.deleted_at is not None


# ---------------------------------------------------------------------------
# 17. One-Use Ticket / Range / Project Isolation API Paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_image_export_endpoints(tmp_path: Path):
    hub_root = tmp_path / "hub"
    store = LocalPathBlobStore(hub_root)

    # Seed a blob
    digest = _put_blob_helper(store, b"export blob content data")

    export_row = PalimpsestImageExport(
        id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
        project_id="test-project-123",
        source_image_id="img-123",
        source_name="ubuntu.raw",
        source_disk_format="raw",
        source_size_bytes=24,
        target_disk_format="qcow2",
        artifact_key="key123",
        result_blob_digest=digest,
        result_size_bytes=24,
        status=STATUS_COMPLETE,
        progress_pct=100,
        created_at=_now(),
        completed_at=_now(),
        deleted_at=None,
    )

    db_store = [export_row]
    fake_redis = FakeRedis()

    async def _mock_get_redis():
        return fake_redis

    service_factory = patch(
        "app.services.palimpsest_image_exports.get_session_factory",
        return_value=FakeSessionFactory(db_store),
    )
    with service_factory:
        with patch("app.api.palimpsest.hub.get_blob_store", return_value=store):
            with patch("app.api.palimpsest.hub._get_redis", new=_mock_get_redis):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    headers={"Authorization": "Bearer test-token"},
                ) as ac:
                    app.dependency_overrides[get_token_info] = lambda: {
                        "project_id": "test-project-123",
                        "user_id": "user-1",
                    }

                    # GET detail
                    resp = await ac.get(f"/api/v1/palimpsest/hub/image-exports/{export_row.id}")
                    assert resp.status_code == 200
                    assert resp.json()["id"] == export_row.id

                    # A different project receives the same project-scoped 404.
                    app.dependency_overrides[get_token_info] = lambda: {
                        "project_id": "other-project",
                        "user_id": "user-2",
                    }
                    resp_other = await ac.get(f"/api/v1/palimpsest/hub/image-exports/{export_row.id}")
                    assert resp_other.status_code == 404
                    app.dependency_overrides[get_token_info] = lambda: {
                        "project_id": "test-project-123",
                        "user_id": "user-1",
                    }

                    # GET blob authenticated
                    resp_blob = await ac.get(f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/blob")
                    assert resp_blob.status_code in (200, 206)
                    assert resp_blob.content == b"export blob content data"

                    # POST download token
                    resp_tok = await ac.post(f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/download-token")
                    assert resp_tok.status_code == 200
                    token_url = resp_tok.json()["url"]
                    token_param = token_url.split("dl_token=")[1]

                    # Unauthenticated GET download with token (1st try -> 200)
                    resp_dl1 = await ac.get(
                        f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/download?dl_token={token_param}"
                    )
                    assert resp_dl1.status_code == 200
                    assert resp_dl1.content == b"export blob content data"

                    # 2nd try with consumed token -> 404 (One-use ticket)
                    resp_dl2 = await ac.get(
                        f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/download?dl_token={token_param}"
                    )
                    assert resp_dl2.status_code == 404

                    # Redis failures fail closed for both token issuance and consumption.
                    fake_redis.fail = True
                    resp_redis_issue = await ac.post(
                        f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/download-token"
                    )
                    assert resp_redis_issue.status_code == 503

                    fake_redis.fail = False
                    resp_redis_token = await ac.post(
                        f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/download-token"
                    )
                    redis_token = resp_redis_token.json()["url"].split("dl_token=")[1]
                    fake_redis.fail = True
                    resp_redis_consume = await ac.get(
                        f"/api/v1/palimpsest/hub/image-exports/{export_row.id}/download?dl_token={redis_token}"
                    )
                    assert resp_redis_consume.status_code == 503

                    app.dependency_overrides.clear()


def _put_blob_helper(store: LocalPathBlobStore, payload: bytes) -> str:
    sha = hashlib.sha256(payload).hexdigest()
    digest = f"sha256:{sha}"
    target = store.blob_path(digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return digest


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}
        self.fail = False

    async def setex(self, key: str, ttl: int, value: str):
        if self.fail:
            raise ConnectionError("Redis unavailable")
        self.data[key] = value

    async def getdel(self, key: str) -> str | None:
        if self.fail:
            raise ConnectionError("Redis unavailable")
        return self.data.pop(key, None)


# ---------------------------------------------------------------------------
# 18. Reference-Aware GC in Export Maintenance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_export_maintenance_reference_aware_gc(tmp_path: Path):
    hub_root = tmp_path / "hub"
    store = LocalPathBlobStore(hub_root)
    store.blobs_dir.mkdir(parents=True, exist_ok=True)
    store.exports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create referenced export blob
    ref_export_digest = _put_blob_helper(store, b"export digest content")

    # 2. Create referenced layer blob
    ref_layer_digest = _put_blob_helper(store, b"layer digest content")

    # 3. Create unreferenced old blob
    unref_digest = _put_blob_helper(store, b"unreferenced content")

    # Set mtime to 2 days ago for all 3 blobs
    old_time = os.path.getmtime(store.blob_path(ref_export_digest)) - 172800
    os.utime(store.blob_path(ref_export_digest), (old_time, old_time))
    os.utime(store.blob_path(ref_layer_digest), (old_time, old_time))
    os.utime(store.blob_path(unref_digest), (old_time, old_time))

    # 4. A recently soft-deleted export keeps its blob during the grace period.
    recent_deleted_digest = _put_blob_helper(store, b"recent deleted export")
    os.utime(store.blob_path(recent_deleted_digest), (old_time, old_time))

    # 5. An export deleted before the grace period no longer keeps its blob.
    expired_deleted_digest = _put_blob_helper(store, b"expired deleted export")
    os.utime(store.blob_path(expired_deleted_digest), (old_time, old_time))

    # Create stale scratch dir
    stale_scratch = store.exports_dir / "stale-job"
    stale_scratch.mkdir(parents=True, exist_ok=True)
    os.utime(stale_scratch, (old_time, old_time))

    export_row = PalimpsestImageExport(
        id="job-1",
        project_id="proj-1",
        source_image_id="img-1",
        source_name="img.raw",
        source_disk_format="raw",
        source_size_bytes=10,
        target_disk_format="qcow2",
        artifact_key="k1",
        result_blob_digest=ref_export_digest,
        status=STATUS_COMPLETE,
        created_at=_now(),
        deleted_at=None,
    )

    recent_deleted_export = PalimpsestImageExport(
        id="job-recently-deleted",
        project_id="proj-1",
        source_image_id="img-2",
        source_name="recent.raw",
        source_disk_format="raw",
        source_size_bytes=10,
        target_disk_format="qcow2",
        artifact_key="k2",
        result_blob_digest=recent_deleted_digest,
        status=STATUS_COMPLETE,
        created_at=_now(),
        deleted_at=_now(),
    )

    expired_deleted_export = PalimpsestImageExport(
        id="job-expired-deleted",
        project_id="proj-1",
        source_image_id="img-3",
        source_name="expired.raw",
        source_disk_format="raw",
        source_size_bytes=10,
        target_disk_format="qcow2",
        artifact_key="k3",
        result_blob_digest=expired_deleted_digest,
        status=STATUS_COMPLETE,
        created_at=_now() - timedelta(days=3),
        deleted_at=_now() - timedelta(days=2),
    )

    layer_row = PalimpsestHubLayer(
        id=1,
        project_id="proj-1",
        blob_digest=ref_layer_digest,
        size_bytes=20,
    )

    db_store = [export_row, recent_deleted_export, expired_deleted_export, layer_row]

    with patch("app.services.palimpsest_image_exports.get_blob_store", return_value=store):
        with patch(
            "app.services.palimpsest_image_exports.get_session_factory", return_value=FakeSessionFactory(db_store)
        ):
            await run_export_maintenance(max_age_seconds=86400)

            # Referenced blobs MUST be preserved
            assert store.blob_path(ref_export_digest).is_file()
            assert store.blob_path(ref_layer_digest).is_file()
            assert store.blob_path(recent_deleted_digest).is_file()

            # Unreferenced old blob MUST be deleted
            assert not store.blob_path(unref_digest).is_file()
            assert not store.blob_path(expired_deleted_digest).is_file()

            # Stale scratch dir MUST be deleted
            assert not stale_scratch.exists()
