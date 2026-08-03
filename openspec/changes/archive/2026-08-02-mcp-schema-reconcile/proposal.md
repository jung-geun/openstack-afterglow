# MCP schema reconciliation

## Why

Repair deployment databases where legacy `CREATE TABLE IF NOT EXISTS` or ORM table creation left existing tables behind the current SQLAlchemy metadata.

## What Changes

- Reconcile every missing table column, index, and unique constraint identified by a deployed-database metadata diff.
- Keep the migration additive and idempotent on MariaDB 10.11+.
- Apply the reconciliation migration to the affected Compose deployment, then exercise the previously failing MCP admin routes.

## Non-goals

- Do not apply migration 069's data-policy updates or deactivate legacy MCP installations.
- Do not add a general automatic migration runner; the existing baseline utility deliberately refuses normal migration execution.
- Do not alter already-present indexes merely because their names differ from SQLAlchemy's implicit names; compare index column signatures.

## Risk controls

- Verify `chat_usage_logs.run_id` has no duplicate non-null values before adding its missing unique key.
- Add only nullable columns or columns with an explicit safe server default.
- Use the backend container's configured database connection so credentials remain inside the deployment.
