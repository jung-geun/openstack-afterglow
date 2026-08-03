-- Preserve microseconds used by v2 approval dispatch and decision HMACs.
ALTER TABLE chat_tool_approvals
    MODIFY COLUMN requested_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    MODIFY COLUMN decided_at DATETIME(6) NULL,
    MODIFY COLUMN expires_at DATETIME(6) NOT NULL;
