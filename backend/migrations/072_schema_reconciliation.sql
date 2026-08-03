-- Reconcile deployment databases where legacy CREATE TABLE IF NOT EXISTS or
-- ORM table creation predated later additive migrations. Every clause is
-- additive and idempotent for MariaDB 10.11+.
--
-- Do not add policy backfills here: this migration restores the current ORM
-- schema only and deliberately excludes migration 069's MCP policy changes.

ALTER TABLE chat_tool_approvals
    ADD COLUMN IF NOT EXISTS preview_fingerprint CHAR(64) NULL AFTER dispatch_hmac,
    ADD COLUMN IF NOT EXISTS decision_hmac CHAR(64) NULL AFTER preview_fingerprint,
    ADD KEY IF NOT EXISTS idx_chat_tool_approvals_pending_expiry (status, expires_at);

ALTER TABLE chat_mcp_servers
    ADD COLUMN IF NOT EXISTS load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand' AFTER is_active;

ALTER TABLE chat_custom_tools
    ADD COLUMN IF NOT EXISTS load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand' AFTER is_active;

ALTER TABLE chat_mcp_servers
    MODIFY COLUMN load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand';

ALTER TABLE chat_custom_tools
    MODIFY COLUMN load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand';

ALTER TABLE mcp_delegated_grants
    ADD COLUMN IF NOT EXISTS orphan_recovery_after DATETIME(6) NULL AFTER cleanup_last_attempt_at,
    ADD COLUMN IF NOT EXISTS orphan_recovery_nonce CHAR(36) NULL AFTER orphan_recovery_after;

ALTER TABLE mcp_oauth_authorization_requests
    ADD COLUMN IF NOT EXISTS grant_id CHAR(36) NULL AFTER grant_deadline;

ALTER TABLE mcp_oauth_authorization_requests
    ADD CONSTRAINT fk_mcp_oauth_requests_grant
        FOREIGN KEY IF NOT EXISTS (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE SET NULL;

ALTER TABLE chat_assets
    ADD KEY IF NOT EXISTS idx_chat_assets_expiry (expires_at);

ALTER TABLE chat_conversations
    ADD KEY IF NOT EXISTS idx_chat_conversations_user_updated (user_id, updated_at);

ALTER TABLE chat_memories
    ADD KEY IF NOT EXISTS idx_chat_memories_scope (user_id, project_id, workspace_id, status, is_active);

ALTER TABLE chat_messages
    ADD KEY IF NOT EXISTS idx_chat_messages_parent (parent_id),
    ADD KEY IF NOT EXISTS idx_chat_messages_conversation_id (conversation_id, id);

ALTER TABLE k3s_clusters
    ADD KEY IF NOT EXISTS ix_k3s_clusters_deleted_at (deleted_at);

ALTER TABLE chat_usage_logs
    ADD UNIQUE KEY IF NOT EXISTS uq_chat_usage_logs_run (run_id);
