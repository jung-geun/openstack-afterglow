"""MariaDB behavior tests for the schema-reconciliation migration."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"
_MIGRATION = Path(__file__).parents[1] / "migrations" / "072_schema_reconciliation.sql"


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


async def test_schema_reconciliation_repairs_legacy_tables_idempotently(db_url: str) -> None:
    prefix = f"schema_reconcile_{uuid.uuid4().hex[:12]}"
    tables = {
        "chat_tool_approvals": f"{prefix}_approvals",
        "chat_mcp_servers": f"{prefix}_mcp_servers",
        "chat_custom_tools": f"{prefix}_custom_tools",
        "mcp_delegated_grants": f"{prefix}_grants",
        "mcp_oauth_authorization_requests": f"{prefix}_oauth_requests",
        "chat_assets": f"{prefix}_assets",
        "chat_conversations": f"{prefix}_conversations",
        "chat_memories": f"{prefix}_memories",
        "chat_messages": f"{prefix}_messages",
        "k3s_clusters": f"{prefix}_clusters",
        "chat_usage_logs": f"{prefix}_usage_logs",
    }

    def temporary_name(name: str) -> str:
        for canonical, temporary in tables.items():
            name = name.replace(canonical, temporary)
        return name

    fk_name = f"fk_{prefix}_oauth_grant"
    migration_sql = _MIGRATION.read_text(encoding="utf-8")
    for canonical, temporary in tables.items():
        migration_sql = migration_sql.replace(canonical, temporary)
    migration_sql = migration_sql.replace("fk_mcp_oauth_requests_grant", fk_name)
    statements = [
        statement.strip()
        for statement in "\n".join(
            line for line in migration_sql.splitlines() if not line.lstrip().startswith("--")
        ).split(";")
        if statement.strip()
    ]

    legacy_ddl = [
        f"""CREATE TABLE `{tables["chat_tool_approvals"]}` (
            run_id CHAR(36) NOT NULL, call_id VARCHAR(190) NOT NULL,
            dispatch_hmac CHAR(64) NULL, status VARCHAR(24) NOT NULL,
            expires_at DATETIME(6) NOT NULL, PRIMARY KEY (run_id, call_id)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{tables["chat_mcp_servers"]}` (
            id BIGINT NOT NULL AUTO_INCREMENT, is_active BOOLEAN NOT NULL DEFAULT TRUE,
            PRIMARY KEY (id)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{tables["chat_custom_tools"]}` (
            id BIGINT NOT NULL AUTO_INCREMENT, is_active BOOLEAN NOT NULL DEFAULT TRUE,
            PRIMARY KEY (id)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{tables["mcp_delegated_grants"]}` (
            id CHAR(36) NOT NULL, cleanup_last_attempt_at DATETIME(6) NULL,
            PRIMARY KEY (id)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{tables["mcp_oauth_authorization_requests"]}` (
            id CHAR(36) NOT NULL, grant_deadline DATETIME(6) NULL,
            PRIMARY KEY (id)
        ) ENGINE=InnoDB""",
        f"CREATE TABLE `{tables['chat_assets']}` (id CHAR(36) NOT NULL, expires_at DATETIME(6) NULL, PRIMARY KEY (id)) ENGINE=InnoDB",
        f"CREATE TABLE `{tables['chat_conversations']}` (id CHAR(36) NOT NULL, user_id VARCHAR(64) NOT NULL, updated_at DATETIME(6) NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB",
        f"CREATE TABLE `{tables['chat_memories']}` (id BIGINT NOT NULL AUTO_INCREMENT, user_id VARCHAR(64) NOT NULL, project_id VARCHAR(64) NULL, workspace_id CHAR(36) NULL, status VARCHAR(20) NOT NULL, is_active BOOLEAN NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB",
        f"CREATE TABLE `{tables['chat_messages']}` (id BIGINT NOT NULL AUTO_INCREMENT, parent_id BIGINT NULL, conversation_id CHAR(36) NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB",
        f"CREATE TABLE `{tables['k3s_clusters']}` (id CHAR(36) NOT NULL, deleted_at DATETIME(6) NULL, PRIMARY KEY (id)) ENGINE=InnoDB",
        f"CREATE TABLE `{tables['chat_usage_logs']}` (id BIGINT NOT NULL AUTO_INCREMENT, run_id CHAR(36) NULL, PRIMARY KEY (id)) ENGINE=InnoDB",
    ]
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)

    try:
        async with engine.begin() as conn:
            for statement in legacy_ddl:
                await conn.execute(text(statement))
            for _ in range(2):
                for statement in statements:
                    await conn.execute(text(statement))

        table_names = tuple(tables.values())
        async with engine.connect() as conn:
            columns = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT table_name, column_name, column_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE() AND table_name IN :table_names
                        """
                        ).bindparams(bindparam("table_names", expanding=True)),
                        {"table_names": table_names},
                    )
                )
                .mappings()
                .all()
            )
            indexes = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT table_name, index_name, non_unique, seq_in_index, column_name
                        FROM information_schema.statistics
                        WHERE table_schema = DATABASE() AND table_name IN :table_names
                          AND index_name <> 'PRIMARY'
                        ORDER BY table_name, index_name, seq_in_index
                        """
                        ).bindparams(bindparam("table_names", expanding=True)),
                        {"table_names": table_names},
                    )
                )
                .mappings()
                .all()
            )
            foreign_keys = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT constraint_name, table_name, column_name,
                               referenced_table_name, referenced_column_name
                        FROM information_schema.key_column_usage
                        WHERE table_schema = DATABASE() AND constraint_name = :constraint_name
                        """
                        ),
                        {"constraint_name": fk_name},
                    )
                )
                .mappings()
                .all()
            )

        actual_columns = {(row["table_name"], row["column_name"]): row for row in columns}
        expected_columns = {
            (tables["chat_tool_approvals"], "preview_fingerprint"): ("char(64)", "YES", "NULL"),
            (tables["chat_tool_approvals"], "decision_hmac"): ("char(64)", "YES", "NULL"),
            (tables["chat_mcp_servers"], "load_policy"): ("varchar(16)", "NO", "'on_demand'"),
            (tables["chat_custom_tools"], "load_policy"): ("varchar(16)", "NO", "'on_demand'"),
            (tables["mcp_delegated_grants"], "orphan_recovery_after"): ("datetime(6)", "YES", "NULL"),
            (tables["mcp_delegated_grants"], "orphan_recovery_nonce"): ("char(36)", "YES", "NULL"),
            (tables["mcp_oauth_authorization_requests"], "grant_id"): ("char(36)", "YES", "NULL"),
        }
        assert {
            key: (row["column_type"], row["is_nullable"], row["column_default"])
            for key, row in actual_columns.items()
            if key in expected_columns
        } == expected_columns

        actual_indexes: dict[tuple[str, str], tuple[bool, tuple[str, ...]]] = {}
        for table_name, index_name in {(row["table_name"], row["index_name"]) for row in indexes}:
            rows = [row for row in indexes if (row["table_name"], row["index_name"]) == (table_name, index_name)]
            actual_indexes[(table_name, index_name)] = (
                rows[0]["non_unique"] == 0,
                tuple(row["column_name"] for row in rows),
            )
        expected_indexes = {
            (tables["chat_tool_approvals"], temporary_name("idx_chat_tool_approvals_pending_expiry")): (
                False,
                ("status", "expires_at"),
            ),
            (tables["chat_assets"], temporary_name("idx_chat_assets_expiry")): (False, ("expires_at",)),
            (tables["chat_conversations"], temporary_name("idx_chat_conversations_user_updated")): (
                False,
                ("user_id", "updated_at"),
            ),
            (tables["chat_memories"], temporary_name("idx_chat_memories_scope")): (
                False,
                ("user_id", "project_id", "workspace_id", "status", "is_active"),
            ),
            (tables["chat_messages"], temporary_name("idx_chat_messages_parent")): (False, ("parent_id",)),
            (tables["chat_messages"], temporary_name("idx_chat_messages_conversation_id")): (
                False,
                ("conversation_id", "id"),
            ),
            (tables["k3s_clusters"], temporary_name("ix_k3s_clusters_deleted_at")): (False, ("deleted_at",)),
            (tables["chat_usage_logs"], temporary_name("uq_chat_usage_logs_run")): (True, ("run_id",)),
        }
        assert {key: actual_indexes[key] for key in expected_indexes} == expected_indexes
        assert foreign_keys == [
            {
                "constraint_name": fk_name,
                "table_name": tables["mcp_oauth_authorization_requests"],
                "column_name": "grant_id",
                "referenced_table_name": tables["mcp_delegated_grants"],
                "referenced_column_name": "id",
            }
        ]
    finally:
        async with engine.begin() as conn:
            for table_name in reversed(tuple(tables.values())):
                await conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
        await engine.dispose()
