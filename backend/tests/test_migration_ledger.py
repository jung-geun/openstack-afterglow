from pathlib import Path

import pytest

from scripts.baseline_migrations import MANIFEST, MigrationLedgerError, baseline_pre037, load_manifest


def test_manifest_has_unique_logical_ids_and_checksums_for_duplicate_numeric_migrations():
    migrations = load_manifest()

    assert len(migrations) == len({migration.logical_id for migration in migrations})
    assert {migration.logical_id for migration in migrations if migration.logical_id.startswith("035-")} == {
        "035-chat-message-reasoning",
        "035-vm-cloud-init-snippets",
    }
    assert all(len(migration.sha256) == 64 for migration in migrations)


def test_manifest_checksum_drift_is_fail_closed(tmp_path: Path):
    original = MANIFEST.read_text(encoding="utf-8")
    altered = original.replace("e4dbc0a2d7e4151ac945d9503a4e5eb3798b1e401b7f3888e05b963ff5e0b297", "0" * 64, 1)
    manifest = tmp_path / "manifest.txt"
    manifest.write_text(altered, encoding="utf-8")

    with pytest.raises(MigrationLedgerError, match="checksum drift"):
        load_manifest(manifest)


async def test_pre037_baseline_is_disabled_without_complete_schema_verifier():
    with pytest.raises(MigrationLedgerError, match="automatic pre-037 baselining is disabled"):
        await baseline_pre037("mysql+aiomysql://unused")
