-- Preserve both the canonical UTC instant and the browser-local wall-clock time for chat messages.
-- `created_timezone` is an IANA zone name; legacy rows intentionally remain NULL.
ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS created_at_local DATETIME(6) NULL AFTER created_at,
    ADD COLUMN IF NOT EXISTS created_timezone VARCHAR(64) NULL AFTER created_at_local;
