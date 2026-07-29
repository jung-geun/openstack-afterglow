-- Durable automatic memory extraction: typed records and per-owner/project serialization.

ALTER TABLE chat_memories
    ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'general' AFTER scope,
    ADD CONSTRAINT chk_chat_memory_category
        CHECK (category IN ('interest', 'development', 'habit', 'preference', 'general'));

CREATE TABLE IF NOT EXISTS chat_memory_owner_locks (
    user_id VARCHAR(64) NOT NULL,
    project_id VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (user_id, project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE chat_jobs
    ADD KEY idx_chat_jobs_kind_claim (kind, status, next_at);
