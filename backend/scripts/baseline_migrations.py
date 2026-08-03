"""Fail-closed migration manifest ledger for Afterglow MySQL schemas.

The runner deliberately never trusts a filename number alone: duplicate numeric migrations
have separate immutable logical identifiers in ``migrations/manifest.txt``. Automatic pre-037
baselining is disabled until a verifier covers every migration-owned schema postcondition.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
_MIGRATION_DIR_CANDIDATES = (SCRIPT_DIR.parent / "migrations", SCRIPT_DIR.parent.parent / "backend" / "migrations")
MIGRATIONS = next(
    (candidate for candidate in _MIGRATION_DIR_CANDIDATES if candidate.is_dir()), _MIGRATION_DIR_CANDIDATES[0]
)
MANIFEST = MIGRATIONS / "manifest.txt"


class MigrationLedgerError(RuntimeError):
    """A manifest, checksum, or production baseline invariant failed."""


@dataclass(frozen=True)
class Migration:
    logical_id: str
    relative_path: str
    sha256: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path = MANIFEST) -> list[Migration]:
    if not path.is_file():
        raise MigrationLedgerError(f"migration manifest is missing: {path}")
    migrations: list[Migration] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if len(fields) != 3:
            raise MigrationLedgerError(f"manifest line {line_number} must contain logical_id|path|sha256")
        logical_id, relative_path, checksum = (field.strip() for field in fields)
        if not logical_id or not relative_path or len(checksum) != 64:
            raise MigrationLedgerError(f"manifest line {line_number} is malformed")
        if logical_id in seen_ids or relative_path in seen_paths:
            raise MigrationLedgerError(f"manifest line {line_number} duplicates an immutable identity")
        resolved = MIGRATIONS / Path(relative_path).name
        if not resolved.is_file():
            raise MigrationLedgerError(f"manifest line {line_number} references an invalid migration path")
        actual = _sha256(resolved)
        if actual != checksum:
            raise MigrationLedgerError(f"checksum drift for {logical_id}: manifest={checksum} actual={actual}")
        seen_ids.add(logical_id)
        seen_paths.add(relative_path)
        migrations.append(Migration(logical_id, relative_path, checksum))
    unlisted_files = {migration.name for migration in MIGRATIONS.glob("*.sql")} - {
        Path(relative_path).name for relative_path in seen_paths
    }
    if unlisted_files:
        raise MigrationLedgerError(f"migration files absent from manifest: {', '.join(sorted(unlisted_files))}")
    if not migrations:
        raise MigrationLedgerError("migration manifest is empty")
    return migrations


async def baseline_pre037(database_url: str) -> None:
    del database_url
    raise MigrationLedgerError(
        "automatic pre-037 baselining is disabled until complete migration-owned schema verification exists"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--baseline-pre037", action="store_true")
    args = parser.parse_args()
    if not args.baseline_pre037:
        parser.error("only --baseline-pre037 is supported; normal migration application remains an explicit operation")
    asyncio.run(baseline_pre037(args.database_url))


if __name__ == "__main__":
    main()
