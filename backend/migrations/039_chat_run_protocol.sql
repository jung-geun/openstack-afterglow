-- 039_chat_run_protocol.sql
-- A1 nullable expansion for canonical encrypted message parts and durable run execution.
-- Legacy content/tool/citation/reasoning columns remain during the A1-A4 rollback window.

ALTER TABLE chat_messages
    ADD COLUMN parts MEDIUMTEXT NULL AFTER attachments,
    ADD COLUMN parts_version INT NULL AFTER parts,
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'complete' AFTER parts_version;

ALTER TABLE chat_conversations
    ADD COLUMN lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'active' AFTER workspace_id,
    ADD COLUMN deleted_at DATETIME NULL AFTER lifecycle_status;

ALTER TABLE user_wallets
    ADD COLUMN reserved_credits DECIMAL(18,8) NOT NULL DEFAULT 0 AFTER used_quota_this_month;

ALTER TABLE chat_usage_logs
    ADD COLUMN run_id CHAR(36) NULL AFTER conversation_id,
    ADD COLUMN usage_components JSON NULL AFTER pricing_snapshot,
    ADD COLUMN provider_reported_cost DECIMAL(20,10) NULL AFTER usage_components,
    ADD UNIQUE KEY uq_chat_usage_logs_run (run_id);

CREATE TABLE chat_runs (
    id CHAR(36) PRIMARY KEY,
    run_scope VARCHAR(20) NOT NULL,
    conversation_id CHAR(36) NULL,
    temp_thread_id CHAR(36) NULL,
    user_message_id BIGINT NULL,
    assistant_message_id BIGINT NULL,
    project_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    model_name VARCHAR(190) NOT NULL,
    agent_id BIGINT NULL,
    capability_snapshot JSON NOT NULL,
    pricing_snapshot JSON NOT NULL,
    request_payload MEDIUMTEXT NULL,
    client_request_id CHAR(36) NOT NULL,
    request_fingerprint VARCHAR(128) NOT NULL,
    fingerprint_version INT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    last_seq BIGINT NOT NULL DEFAULT 0,
    current_ordinal INT NOT NULL DEFAULT 0,
    lease_owner VARCHAR(190) NULL,
    lease_expires_at DATETIME NULL,
    provider_started_at DATETIME NULL,
    cancel_requested_at DATETIME NULL,
    finalizer_lease_owner VARCHAR(190) NULL,
    finalizer_lease_expires_at DATETIME NULL,
    reserved_credits DECIMAL(18,8) NOT NULL DEFAULT 0,
    reservation_released_at DATETIME NULL,
    usage_reconciled_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_chat_runs_owner_status (project_id, user_id, status),
    KEY idx_chat_runs_conversation_status (conversation_id, status),
    KEY idx_chat_runs_temp_status (temp_thread_id, status),
    UNIQUE KEY uq_chat_runs_idempotency (project_id, user_id, client_request_id),
    CONSTRAINT fk_chat_runs_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_runs_user_message FOREIGN KEY (user_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_runs_assistant_message FOREIGN KEY (assistant_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
);

CREATE TABLE chat_run_providers (
    run_id CHAR(36) NOT NULL,
    purpose VARCHAR(30) NOT NULL,
    provider_id BIGINT NULL,
    model_id BIGINT NULL,
    provider_label VARCHAR(190) NOT NULL,
    model_label VARCHAR(190) NOT NULL,
    config_version_hash VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, purpose),
    CONSTRAINT fk_chat_run_providers_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_run_providers_provider FOREIGN KEY (provider_id) REFERENCES llm_providers(id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_run_providers_model FOREIGN KEY (model_id) REFERENCES llm_models(id) ON DELETE SET NULL
);

CREATE TABLE chat_run_events (
    run_id CHAR(36) NOT NULL,
    seq BIGINT NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    payload MEDIUMTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, seq),
    CONSTRAINT fk_chat_run_events_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE
);

CREATE TABLE chat_tool_approvals (
    run_id CHAR(36) NOT NULL,
    call_id VARCHAR(190) NOT NULL,
    tool_name MEDIUMTEXT NOT NULL,
    arguments MEDIUMTEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at DATETIME NULL,
    expires_at DATETIME NOT NULL,
    PRIMARY KEY (run_id, call_id),
    CONSTRAINT fk_chat_tool_approvals_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE
);

CREATE TABLE chat_temp_threads (
    id CHAR(36) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    history MEDIUMTEXT NOT NULL,
    active_run_id CHAR(36) NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_chat_temp_threads_owner_expiry (project_id, user_id, expires_at)
);

ALTER TABLE chat_runs
    ADD CONSTRAINT fk_chat_runs_temp_thread FOREIGN KEY (temp_thread_id) REFERENCES chat_temp_threads(id) ON DELETE SET NULL;

ALTER TABLE chat_temp_threads
    ADD CONSTRAINT fk_chat_temp_threads_active_run FOREIGN KEY (active_run_id) REFERENCES chat_runs(id) ON DELETE SET NULL;

CREATE TABLE chat_scheduler_leases (
    scheduler_name VARCHAR(100) PRIMARY KEY,
    owner VARCHAR(190) NOT NULL,
    expires_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE chat_run_turns (
    run_id CHAR(36) NOT NULL,
    ordinal INT NOT NULL,
    assistant_message_id BIGINT NULL,
    message_event_seq BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, ordinal),
    UNIQUE KEY uq_chat_run_turn_message_event (run_id, message_event_seq),
    CONSTRAINT fk_chat_run_turns_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_run_turns_message FOREIGN KEY (assistant_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
);

CREATE TABLE chat_run_segments (
    run_id CHAR(36) NOT NULL,
    segment_id VARCHAR(190) NOT NULL,
    ordinal INT NOT NULL,
    endpoint VARCHAR(40) NOT NULL,
    turn_ordinal INT NULL,
    call_id VARCHAR(190) NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'prepared',
    provider_started_at DATETIME NULL,
    result_payload MEDIUMTEXT NULL,
    usage_payload MEDIUMTEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    PRIMARY KEY (run_id, segment_id),
    UNIQUE KEY uq_chat_run_segments_ordinal (run_id, ordinal),
    CONSTRAINT fk_chat_run_segments_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE
);
