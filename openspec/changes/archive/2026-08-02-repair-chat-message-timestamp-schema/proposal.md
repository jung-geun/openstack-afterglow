## Why

The deployed chat API returns 503 for conversation messages because its ORM selects `chat_messages.created_at_local`, while the serving MariaDB schema does not contain that column. The application image has deployed ahead of the additive timestamp migration.

## What Changes

- Apply `070_chat_message_local_timestamps.sql` to the affected deployment database.
- Verify both timestamp columns are present and the previously failing conversation-message endpoint succeeds.
- Preserve the migration manifest entry and existing idempotent `ADD COLUMN IF NOT EXISTS` semantics; do not make the ORM silently tolerate a missing required schema migration.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Existing deployment database gains browser-local message timestamp storage compatible with the deployed chat ORM.

## Impact

- `chat_messages` gains nullable `created_at_local DATETIME(6)` and `created_timezone VARCHAR(64)` columns. Legacy rows remain valid with NULL values.
- No application or API contract change is required.
