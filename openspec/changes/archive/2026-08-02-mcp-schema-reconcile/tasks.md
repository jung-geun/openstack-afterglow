## Implementation Tasks

- [x] Diff the deployed Compose database against `Base.metadata` for tables, columns, indexes, and unique constraints.
- [x] Confirm `chat_usage_logs.run_id` has no duplicate non-null values before adding its unique key.
- [x] Add a manifest-tracked, additive reconciliation migration for every confirmed schema gap.
- [x] Apply the migration to the affected Compose database through the backend container.
- [x] Verify the MCP cleanup query and the previously failing MCP server/custom-tool administration routes.
- [x] Run focused tests and the required full test and lint gates.

## Evidence

- A signature-based diff of the deployed backend database against `Base.metadata` initially found seven missing columns, seven missing index signatures, and one missing unique key; after applying migration 072 through the backend container, it reported no missing tables, columns, indexes, unique constraints, or foreign keys.
- The exact MCP cleanup query completed with zero work, and in-container FastAPI requests to `/api/v1/chat/admin/mcp-servers` and `/api/v1/chat/admin/custom-tools` returned `200` with one and zero records, respectively.
- `npm run test:db` passed 65 MariaDB tests including `test_schema_reconciliation_repairs_legacy_tables_idempotently`; `npm run test:all` passed 3,884 unit, 195 integration, and 928 frontend tests; `npm run lint:backend` passed.
