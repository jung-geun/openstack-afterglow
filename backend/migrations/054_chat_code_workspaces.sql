-- 054_chat_code_workspaces.sql
-- Project-scoped remote code workspaces and write-only Git credentials.

CREATE TABLE chat_git_credentials (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    host VARCHAR(255) NOT NULL,
    username VARCHAR(255) NULL,
    token_ciphertext MEDIUMTEXT NOT NULL,
    credential_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    revoked_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_git_credentials_owner_host (owner_user_id, owner_project_id, host),
    KEY idx_chat_git_credentials_owner (owner_user_id, owner_project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_code_workspaces (
    id CHAR(36) PRIMARY KEY,
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    name VARCHAR(100) NOT NULL,
    source_kind VARCHAR(10) NOT NULL,
    repository_url VARCHAR(2048) NULL,
    source_revision VARCHAR(255) NULL,
    resolved_base_commit_sha CHAR(64) NULL,
    working_branch VARCHAR(255) NOT NULL,
    credential_id BIGINT NULL,
    credential_version BIGINT UNSIGNED NULL,
    runtime_workspace_id VARCHAR(255) NULL,
    lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'creating',
    state_revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
    runtime_capabilities JSON NULL,
    image_digest VARCHAR(255) NOT NULL,
    policy_fingerprint CHAR(64) NOT NULL,
    writer_lease_owner VARCHAR(190) NULL,
    writer_lease_expires_at DATETIME NULL,
    writer_fence BIGINT UNSIGNED NOT NULL DEFAULT 0,
    expires_at DATETIME NOT NULL,
    error_code VARCHAR(100) NULL,
    request_fingerprint CHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_code_workspaces_request (owner_user_id, owner_project_id, request_fingerprint),
    KEY idx_chat_code_workspaces_owner_status (owner_user_id, owner_project_id, lifecycle_status),
    KEY idx_chat_code_workspaces_expiry (expires_at, lifecycle_status),
    CONSTRAINT fk_chat_code_workspaces_credential FOREIGN KEY (credential_id) REFERENCES chat_git_credentials(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_code_workspace_assets (
    workspace_id CHAR(36) NOT NULL,
    asset_id CHAR(36) NOT NULL,
    purpose VARCHAR(30) NOT NULL,
    state_revision BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, asset_id, purpose),

    CONSTRAINT fk_chat_code_workspace_assets_workspace FOREIGN KEY (workspace_id) REFERENCES chat_code_workspaces(id) ON DELETE RESTRICT,
    CONSTRAINT fk_chat_code_workspace_assets_asset FOREIGN KEY (asset_id) REFERENCES chat_assets(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
ALTER TABLE chat_conversations
    ADD COLUMN code_workspace_id CHAR(36) NULL AFTER workspace_id,
    ADD KEY idx_chat_conversations_code_workspace (code_workspace_id),
    ADD CONSTRAINT fk_chat_conversations_code_workspace FOREIGN KEY (code_workspace_id) REFERENCES chat_code_workspaces(id) ON DELETE SET NULL;


ALTER TABLE chat_runs
    ADD CONSTRAINT fk_chat_runs_code_workspace FOREIGN KEY (code_workspace_id) REFERENCES chat_code_workspaces(id) ON DELETE SET NULL;
