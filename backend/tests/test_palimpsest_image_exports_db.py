"""MariaDB DDL parity checks for the Palimpsest image export migration."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.db import PalimpsestImageExport

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"
_MIGRATION = Path(__file__).parents[1] / "migrations" / "070_palimpsest_image_exports.sql"


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


async def test_migration_070_matches_export_orm_contract(db_url: str) -> None:
    """Apply the production SQL to MariaDB, then compare its live shape with the ORM."""
    table_name = f"palimpsest_export_migration_{uuid.uuid4().hex[:12]}"
    migration_sql = _MIGRATION.read_text(encoding="utf-8").replace("palimpsest_image_exports", table_name)
    migration_sql = "\n".join(line for line in migration_sql.splitlines() if not line.lstrip().startswith("--"))
    statements = [statement.strip() for statement in migration_sql.split(";") if statement.strip()]
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)

    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))

        async with engine.connect() as conn:
            column_rows = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE,
                               COLUMN_DEFAULT, CHARACTER_MAXIMUM_LENGTH, DATETIME_PRECISION
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE() AND table_name = :table_name
                        ORDER BY ORDINAL_POSITION
                        """
                        ),
                        {"table_name": table_name},
                    )
                )
                .mappings()
                .all()
            )
            index_rows = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
                        FROM information_schema.statistics
                        WHERE table_schema = DATABASE() AND table_name = :table_name
                          AND INDEX_NAME <> 'PRIMARY'
                        ORDER BY INDEX_NAME, SEQ_IN_INDEX
                        """
                        ),
                        {"table_name": table_name},
                    )
                )
                .mappings()
                .all()
            )

            await conn.execute(
                text(
                    f"""
                    INSERT INTO `{table_name}` (
                        id, project_id, source_image_id, source_name,
                        source_disk_format, source_size_bytes,
                        source_fingerprint, artifact_key, target_disk_format,
                        next_at, created_at, updated_at
                    ) VALUES (
                        :id, :project_id, :source_image_id, :source_name,
                        :source_disk_format, :source_size_bytes,
                        :source_fingerprint, :artifact_key, :target_disk_format,
                        NOW(6), NOW(6), NOW(6)
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "project_id": "migration-project",
                    "source_image_id": "migration-image",
                    "source_name": "migration.raw",
                    "source_disk_format": "raw",
                    "source_size_bytes": 1024,
                    "source_fingerprint": "a" * 64,
                    "artifact_key": "b" * 64,
                    "target_disk_format": "qcow2",
                },
            )
            defaults = (
                (await conn.execute(text(f"SELECT status, progress_pct, attempts FROM `{table_name}` LIMIT 1")))
                .mappings()
                .one()
            )

        orm_table = PalimpsestImageExport.__table__
        actual_columns = {row["COLUMN_NAME"]: row for row in column_rows}
        assert set(actual_columns) == set(orm_table.columns.keys())

        for orm_column in orm_table.columns:
            actual = actual_columns[orm_column.name]
            assert (actual["IS_NULLABLE"] == "YES") is orm_column.nullable
            if getattr(orm_column.type, "length", None) is not None:
                assert actual["CHARACTER_MAXIMUM_LENGTH"] == orm_column.type.length

        datetime_columns = {
            "next_at",
            "lease_expires_at",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "deleted_at",
        }
        assert {name for name, row in actual_columns.items() if row["DATA_TYPE"] == "datetime"} == datetime_columns
        assert all(actual_columns[name]["DATETIME_PRECISION"] == 6 for name in datetime_columns)
        assert actual_columns["source_size_bytes"]["DATA_TYPE"] == "bigint"
        assert actual_columns["result_size_bytes"]["DATA_TYPE"] == "bigint"
        assert actual_columns["progress_pct"]["DATA_TYPE"] == "int"
        assert actual_columns["error_message"]["DATA_TYPE"] == "text"
        assert dict(defaults) == {"status": "queued", "progress_pct": 0, "attempts": 0}

        expected_indexes = {
            "uq_palimpsest_exports_project_artifact": (True, ("project_id", "artifact_key")),
            "idx_palimpsest_exports_artifact": (False, ("artifact_key",)),
            "idx_palimpsest_exports_digest": (False, ("result_blob_digest",)),
            "idx_palimpsest_exports_claim": (False, ("status", "next_at")),
            "idx_palimpsest_exports_project_created": (False, ("project_id", "deleted_at", "created_at")),
        }
        orm_indexes = {
            index.name: (bool(index.unique), tuple(column.name for column in index.columns))
            for index in orm_table.indexes
        }
        orm_indexes.update(
            {
                constraint.name: (True, tuple(column.name for column in constraint.columns))
                for constraint in orm_table.constraints
                if constraint.name and constraint.name.startswith("uq_")
            }
        )
        assert orm_indexes == expected_indexes

        actual_indexes: dict[str, tuple[bool, tuple[str, ...]]] = {}
        for index_name in {row["INDEX_NAME"] for row in index_rows}:
            rows = [row for row in index_rows if row["INDEX_NAME"] == index_name]
            actual_indexes[index_name] = (
                rows[0]["NON_UNIQUE"] == 0,
                tuple(row["COLUMN_NAME"] for row in rows),
            )
        assert actual_indexes == expected_indexes
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
        await engine.dispose()
