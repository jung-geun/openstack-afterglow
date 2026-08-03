-- Bind durable v2 approval previews and decisions to their frozen dispatch identity.
-- Existing paused approvals without these fields fail closed on resume.

ALTER TABLE chat_tool_approvals
    ADD COLUMN IF NOT EXISTS preview_fingerprint CHAR(64) NULL AFTER dispatch_hmac,
    ADD COLUMN IF NOT EXISTS decision_hmac CHAR(64) NULL AFTER preview_fingerprint;
