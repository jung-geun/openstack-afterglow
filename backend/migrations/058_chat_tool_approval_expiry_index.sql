-- 058_chat_tool_approval_expiry_index.sql
-- Supports bounded worker sweeps of pending v2 approval expirations.

ALTER TABLE chat_tool_approvals
    ADD KEY idx_chat_tool_approvals_pending_expiry (status, expires_at);
