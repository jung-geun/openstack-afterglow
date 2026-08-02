## Implementation Tasks

- [x] Document the required schema-migration procedure for image upgrades.
- [x] Confirm the affected deployment database is missing the two timestamp columns and identify the deployment access path.
- [x] Apply the manifest-tracked, idempotent timestamp migration to that database.
- [x] Verify the conversation messages endpoint and record the outcome.

## Evidence

- 2026-08-02: Probed `afterglow-dev`'s backend database through its configured application connection. Both timestamp columns were absent. Applied `070_chat_message_local_timestamps.sql`'s additive DDL, then verified `created_at_local DATETIME(6) NULL` and `created_timezone VARCHAR(64) NULL` are present.
- 2026-08-02: Executed the same `list_message_tree` query used by the affected messages endpoint against the reported conversation after migration; it returned four messages successfully instead of raising the prior `Unknown column` error.
