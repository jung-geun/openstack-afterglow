-- 040_chat_jobs_memory.sql
-- Durable postprocess jobs, server-produced asset derivations, and MySQL memory outbox.

CREATE TABLE chat_jobs (
    id CHAR(36) PRIMARY KEY,
    kind VARCHAR(40) NOT NULL,
    run_id CHAR(36) NULL,
    conversation_id CHAR(36) NULL,
    memory_id BIGINT NULL,
    asset_id CHAR(36) NULL,
    payload MEDIUMTEXT NULL,
    progress JSON NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    lease_owner VARCHAR(190) NULL,
    lease_expires_at DATETIME NULL,
    attempts INT NOT NULL DEFAULT 0,
    next_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_code VARCHAR(100) NULL,
    idempotency_key VARCHAR(190) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_jobs_idempotency (idempotency_key),
    KEY idx_chat_jobs_claim (status, next_at),
    CONSTRAINT fk_chat_jobs_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_jobs_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_jobs_asset FOREIGN KEY (asset_id) REFERENCES chat_assets(id) ON DELETE SET NULL
);

CREATE TABLE chat_input_derivations (
    id CHAR(36) PRIMARY KEY,
    message_id BIGINT NULL,
    temp_thread_id CHAR(36) NULL,
    turn_ordinal INT NULL,
    part_index INT NOT NULL,
    asset_id CHAR(36) NOT NULL,
    asset_sha256 CHAR(64) NOT NULL,
    kind VARCHAR(30) NOT NULL,
    content MEDIUMTEXT NULL,
    producer_model VARCHAR(190) NULL,
    producer_version VARCHAR(190) NULL,
    usage_segment_id VARCHAR(190) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_input_derivation (message_id, temp_thread_id, turn_ordinal, part_index, asset_sha256, kind),
    CONSTRAINT fk_chat_input_derivations_message FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_input_derivations_asset FOREIGN KEY (asset_id) REFERENCES chat_assets(id) ON DELETE RESTRICT
);

ALTER TABLE chat_memories
    ADD COLUMN project_id VARCHAR(64) NULL AFTER user_id,
    ADD COLUMN workspace_id BIGINT NULL AFTER project_id,
    ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'account' AFTER workspace_id,
    ADD COLUMN confidence DECIMAL(5,4) NULL AFTER scope,
    ADD COLUMN expires_at DATETIME NULL AFTER confidence,
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active' AFTER expires_at,
    ADD COLUMN extraction_status VARCHAR(20) NULL AFTER status;

CREATE TABLE chat_memory_provenance (
    memory_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    conversation_id CHAR(36) NOT NULL,
    source_type VARCHAR(30) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (memory_id, message_id, source_type),
    CONSTRAINT fk_chat_memory_provenance_memory FOREIGN KEY (memory_id) REFERENCES chat_memories(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_memory_provenance_message FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_memory_provenance_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
);

CREATE TABLE chat_memory_outbox (
    change_seq BIGINT NOT NULL AUTO_INCREMENT,
    event_key VARCHAR(190) NOT NULL,
    memory_id BIGINT NOT NULL,
    mutation VARCHAR(20) NOT NULL,
    content_hash CHAR(64) NOT NULL,
    required_generations JSON NOT NULL,
    applied_generations JSON NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    lease_owner VARCHAR(190) NULL,
    lease_expires_at DATETIME NULL,
    attempts INT NOT NULL DEFAULT 0,
    error_code VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (change_seq),
    UNIQUE KEY uq_chat_memory_outbox_event (event_key),
    KEY idx_chat_memory_outbox_claim (status, change_seq),
    CONSTRAINT fk_chat_memory_outbox_memory FOREIGN KEY (memory_id) REFERENCES chat_memories(id) ON DELETE RESTRICT
);
