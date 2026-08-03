-- 053_chat_agent_run_protocol.sql
-- Additive v2 executor metadata. Existing v1 rows remain protocol version 1 until drained.

ALTER TABLE chat_runs
    ADD COLUMN execution_protocol_version TINYINT UNSIGNED NOT NULL DEFAULT 1 AFTER fingerprint_version,
    ADD COLUMN execution_mode VARCHAR(10) NOT NULL DEFAULT 'chat' AFTER execution_protocol_version,
    ADD COLUMN code_workspace_id CHAR(36) NULL AFTER agent_id,
    ADD COLUMN parent_run_id CHAR(36) NULL AFTER code_workspace_id,
    ADD COLUMN root_run_id CHAR(36) NULL AFTER parent_run_id,
    ADD COLUMN delegation_call_id VARCHAR(190) NULL AFTER root_run_id,
    ADD COLUMN depth TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER delegation_call_id,
    ADD COLUMN policy_snapshot JSON NULL AFTER capability_snapshot,
    ADD COLUMN reservation_snapshot JSON NULL AFTER pricing_snapshot,
    ADD COLUMN descendant_credit_ceiling DECIMAL(18,8) NULL AFTER reserved_credits,
    ADD COLUMN descendant_credits_reserved DECIMAL(18,8) NOT NULL DEFAULT 0 AFTER descendant_credit_ceiling,
    ADD COLUMN sandbox_seconds_ceiling INT UNSIGNED NULL AFTER descendant_credits_reserved,
    ADD COLUMN sandbox_seconds_reserved INT UNSIGNED NOT NULL DEFAULT 0 AFTER sandbox_seconds_ceiling,
    ADD KEY idx_chat_runs_root_status (root_run_id, status),
    ADD KEY idx_chat_runs_parent_status (parent_run_id, status),
    ADD UNIQUE KEY uq_chat_runs_parent_delegation (parent_run_id, delegation_call_id),
    ADD CONSTRAINT fk_chat_runs_parent_run FOREIGN KEY (parent_run_id) REFERENCES chat_runs(id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_chat_runs_root_run FOREIGN KEY (root_run_id) REFERENCES chat_runs(id) ON DELETE RESTRICT;

ALTER TABLE chat_tool_approvals
    ADD COLUMN arguments_ciphertext MEDIUMTEXT NULL AFTER arguments,
    ADD COLUMN dispatch_hmac CHAR(64) NULL AFTER arguments_ciphertext,
    ADD COLUMN source VARCHAR(30) NULL AFTER tool_name,
    ADD COLUMN effect VARCHAR(30) NULL AFTER source,
    ADD COLUMN tool_definition_hash CHAR(64) NULL AFTER effect,
    ADD COLUMN config_fingerprint CHAR(64) NULL AFTER tool_definition_hash,
    ADD COLUMN destination_origin VARCHAR(255) NULL AFTER config_fingerprint,
    ADD COLUMN expected_state_revision BIGINT UNSIGNED NULL AFTER destination_origin,
    ADD COLUMN writer_fence BIGINT UNSIGNED NULL AFTER expected_state_revision,
    ADD COLUMN decided_by_user_id VARCHAR(64) NULL AFTER decided_at;

ALTER TABLE chat_run_segments
    ADD COLUMN kind VARCHAR(40) NOT NULL DEFAULT 'provider' AFTER endpoint,
    ADD COLUMN boundary_key VARCHAR(255) NULL AFTER kind,
    ADD UNIQUE KEY uq_chat_run_segments_boundary (run_id, boundary_key);

CREATE TABLE chat_run_interactions (
    run_id CHAR(36) NOT NULL,
    id CHAR(36) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    request_ciphertext MEDIUMTEXT NOT NULL,
    response_ciphertext MEDIUMTEXT NULL,
    response_schema JSON NOT NULL,
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at DATETIME NULL,
    decided_by_user_id VARCHAR(64) NULL,
    expires_at DATETIME NOT NULL,
    PRIMARY KEY (run_id, id),
    KEY idx_chat_run_interactions_pending_expiry (status, expires_at),
    CONSTRAINT fk_chat_run_interactions_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_context_checkpoints (
    id CHAR(36) PRIMARY KEY,
    run_id CHAR(36) NOT NULL,
    conversation_id CHAR(36) NULL,
    source_anchor_message_id BIGINT NULL,
    source_hashes JSON NOT NULL,
    summary_ciphertext MEDIUMTEXT NOT NULL,
    token_estimate INT UNSIGNED NOT NULL,
    context_limit INT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_chat_context_checkpoints_run (run_id),
    KEY idx_chat_context_checkpoints_conversation_anchor (conversation_id, source_anchor_message_id),
    CONSTRAINT fk_chat_context_checkpoints_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_context_checkpoints_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_context_checkpoints_anchor FOREIGN KEY (source_anchor_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
