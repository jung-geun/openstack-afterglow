-- 056_chat_agent_platform_schema_reconcile.sql
-- Reconcile databases where database_auto_create_tables created new v2 tables
-- before migrations 053-055 altered pre-existing chat tables. Every clause is
-- additive and idempotent for MariaDB 10.11+.

ALTER TABLE chat_runs
    ADD COLUMN IF NOT EXISTS execution_protocol_version TINYINT UNSIGNED NOT NULL DEFAULT 1 AFTER fingerprint_version,
    ADD COLUMN IF NOT EXISTS execution_mode VARCHAR(10) NOT NULL DEFAULT 'chat' AFTER execution_protocol_version,
    ADD COLUMN IF NOT EXISTS code_workspace_id CHAR(36) NULL AFTER agent_id,
    ADD COLUMN IF NOT EXISTS parent_run_id CHAR(36) NULL AFTER code_workspace_id,
    ADD COLUMN IF NOT EXISTS root_run_id CHAR(36) NULL AFTER parent_run_id,
    ADD COLUMN IF NOT EXISTS delegation_call_id VARCHAR(190) NULL AFTER root_run_id,
    ADD COLUMN IF NOT EXISTS depth TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER delegation_call_id,
    ADD COLUMN IF NOT EXISTS policy_snapshot JSON NULL AFTER capability_snapshot,
    ADD COLUMN IF NOT EXISTS reservation_snapshot JSON NULL AFTER pricing_snapshot,
    ADD COLUMN IF NOT EXISTS descendant_credit_ceiling DECIMAL(18,8) NULL AFTER reserved_credits,
    ADD COLUMN IF NOT EXISTS descendant_credits_reserved DECIMAL(18,8) NOT NULL DEFAULT 0 AFTER descendant_credit_ceiling,
    ADD COLUMN IF NOT EXISTS sandbox_seconds_ceiling INT UNSIGNED NULL AFTER descendant_credits_reserved,
    ADD COLUMN IF NOT EXISTS sandbox_seconds_reserved INT UNSIGNED NOT NULL DEFAULT 0 AFTER sandbox_seconds_ceiling,
    ADD KEY IF NOT EXISTS idx_chat_runs_root_status (root_run_id, status),
    ADD KEY IF NOT EXISTS idx_chat_runs_parent_status (parent_run_id, status),
    ADD UNIQUE KEY IF NOT EXISTS uq_chat_runs_parent_delegation (parent_run_id, delegation_call_id),
    ADD CONSTRAINT fk_chat_runs_parent_run FOREIGN KEY IF NOT EXISTS (parent_run_id) REFERENCES chat_runs(id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_chat_runs_root_run FOREIGN KEY IF NOT EXISTS (root_run_id) REFERENCES chat_runs(id) ON DELETE RESTRICT;

ALTER TABLE chat_tool_approvals
    ADD COLUMN IF NOT EXISTS arguments_ciphertext MEDIUMTEXT NULL AFTER arguments,
    ADD COLUMN IF NOT EXISTS dispatch_hmac CHAR(64) NULL AFTER arguments_ciphertext,
    ADD COLUMN IF NOT EXISTS source VARCHAR(30) NULL AFTER tool_name,
    ADD COLUMN IF NOT EXISTS effect VARCHAR(30) NULL AFTER source,
    ADD COLUMN IF NOT EXISTS tool_definition_hash CHAR(64) NULL AFTER effect,
    ADD COLUMN IF NOT EXISTS config_fingerprint CHAR(64) NULL AFTER tool_definition_hash,
    ADD COLUMN IF NOT EXISTS destination_origin VARCHAR(255) NULL AFTER config_fingerprint,
    ADD COLUMN IF NOT EXISTS expected_state_revision BIGINT UNSIGNED NULL AFTER destination_origin,
    ADD COLUMN IF NOT EXISTS writer_fence BIGINT UNSIGNED NULL AFTER expected_state_revision,
    ADD COLUMN IF NOT EXISTS decided_by_user_id VARCHAR(64) NULL AFTER decided_at;

ALTER TABLE chat_run_segments
    ADD COLUMN IF NOT EXISTS kind VARCHAR(40) NOT NULL DEFAULT 'provider' AFTER endpoint,
    ADD COLUMN IF NOT EXISTS boundary_key VARCHAR(255) NULL AFTER kind,
    ADD UNIQUE KEY IF NOT EXISTS uq_chat_run_segments_boundary (run_id, boundary_key);

ALTER TABLE chat_conversations
    ADD COLUMN IF NOT EXISTS code_workspace_id CHAR(36) NULL AFTER workspace_id,
    ADD KEY IF NOT EXISTS idx_chat_conversations_code_workspace (code_workspace_id),
    ADD CONSTRAINT fk_chat_conversations_code_workspace FOREIGN KEY IF NOT EXISTS (code_workspace_id) REFERENCES chat_code_workspaces(id) ON DELETE SET NULL;

ALTER TABLE chat_runs
    ADD CONSTRAINT fk_chat_runs_code_workspace FOREIGN KEY IF NOT EXISTS (code_workspace_id) REFERENCES chat_code_workspaces(id) ON DELETE SET NULL;

ALTER TABLE chat_skills
    ADD COLUMN IF NOT EXISTS project_id VARCHAR(64) NULL AFTER owner_project_id,
    ADD COLUMN IF NOT EXISTS slug VARCHAR(100) NULL AFTER name,
    ADD COLUMN IF NOT EXISTS argument_hint VARCHAR(500) NULL AFTER description,
    ADD COLUMN IF NOT EXISTS user_invocable BOOLEAN NOT NULL DEFAULT TRUE AFTER argument_hint,
    ADD COLUMN IF NOT EXISTS model_invocable BOOLEAN NOT NULL DEFAULT FALSE AFTER user_invocable,
    ADD COLUMN IF NOT EXISTS content_hash CHAR(64) NULL AFTER instructions,
    ADD COLUMN IF NOT EXISTS source_package_id CHAR(36) NULL AFTER content_hash,
    ADD COLUMN IF NOT EXISTS source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN IF NOT EXISTS managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY IF NOT EXISTS idx_chat_skills_project (project_id),
    ADD UNIQUE KEY IF NOT EXISTS uq_chat_skills_project_slug (project_id, slug);
UPDATE chat_skills SET project_id = owner_project_id WHERE project_id IS NULL;

ALTER TABLE chat_agents
    ADD COLUMN IF NOT EXISTS project_id VARCHAR(64) NULL AFTER owner_user_id,
    ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'general' AFTER visibility,
    ADD COLUMN IF NOT EXISTS execution_policy JSON NULL AFTER role,
    ADD COLUMN IF NOT EXISTS delegable_agent_ids JSON NULL AFTER execution_policy,
    ADD COLUMN IF NOT EXISTS skill_ids JSON NULL AFTER tool_ids,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER clone_count,
    ADD COLUMN IF NOT EXISTS content_hash CHAR(64) NULL AFTER instructions,
    ADD COLUMN IF NOT EXISTS source_package_id CHAR(36) NULL AFTER content_hash,
    ADD COLUMN IF NOT EXISTS source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN IF NOT EXISTS managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY IF NOT EXISTS idx_chat_agents_project (project_id),
    ADD KEY IF NOT EXISTS idx_chat_agents_project_active (project_id, is_active);

ALTER TABLE chat_custom_tools
    ADD COLUMN IF NOT EXISTS project_id VARCHAR(64) NULL AFTER owner_project_id,
    ADD COLUMN IF NOT EXISTS effect VARCHAR(30) NOT NULL DEFAULT 'external_mutation' AFTER timeout_seconds,
    ADD COLUMN IF NOT EXISTS config_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER effect,
    ADD COLUMN IF NOT EXISTS source_package_id CHAR(36) NULL AFTER config_version,
    ADD COLUMN IF NOT EXISTS source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN IF NOT EXISTS managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY IF NOT EXISTS idx_chat_custom_tools_project (project_id);
UPDATE chat_custom_tools SET project_id = owner_project_id WHERE project_id IS NULL;

ALTER TABLE chat_mcp_servers
    ADD COLUMN IF NOT EXISTS project_id VARCHAR(64) NULL AFTER owner_project_id,
    ADD COLUMN IF NOT EXISTS tool_effect_overrides JSON NULL AFTER auth_requirements,
    ADD COLUMN IF NOT EXISTS config_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER tool_effect_overrides,
    ADD COLUMN IF NOT EXISTS source_package_id CHAR(36) NULL AFTER config_version,
    ADD COLUMN IF NOT EXISTS source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN IF NOT EXISTS managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY IF NOT EXISTS idx_chat_mcp_servers_project (project_id);
UPDATE chat_mcp_servers SET project_id = owner_project_id WHERE project_id IS NULL;

ALTER TABLE chat_mcp_credentials
    ADD COLUMN IF NOT EXISTS credential_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER encrypted_values,
    ADD COLUMN IF NOT EXISTS revoked_at DATETIME NULL AFTER credential_version;
