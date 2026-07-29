-- Per-user OAuth connections for remote streamable-HTTP MCP servers.
-- Tokens and dynamic-client secrets are AES-256-GCM ciphertexts; metadata remains non-secret.

ALTER TABLE chat_mcp_servers
    ADD COLUMN IF NOT EXISTS auth_mode VARCHAR(12) NOT NULL DEFAULT 'none' AFTER auth_requirements;

UPDATE chat_mcp_servers
SET auth_mode = 'headers'
WHERE auth_requirements IS NOT NULL
  AND JSON_LENGTH(auth_requirements) > 0
  AND auth_mode = 'none';

-- The hosted Notion MCP accepts only user OAuth, never static bearer integration tokens.
UPDATE chat_mcp_servers
SET auth_mode = 'oauth'
WHERE LOWER(TRIM(url)) = 'https://mcp.notion.com/mcp';

CREATE TABLE IF NOT EXISTS chat_mcp_oauth_connections (
    id CHAR(36) NOT NULL,
    mcp_server_id BIGINT NOT NULL,
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    encrypted_tokens MEDIUMTEXT NOT NULL,
    credential_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    status VARCHAR(12) NOT NULL DEFAULT 'active',
    expires_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_chat_mcp_oauth_connection (mcp_server_id, owner_user_id, owner_project_id),
    KEY idx_chat_mcp_oauth_connection_owner (owner_user_id, owner_project_id, status),
    CONSTRAINT chk_chat_mcp_oauth_connection_status CHECK (status IN ('active', 'revoked')),
    CONSTRAINT fk_chat_mcp_oauth_connection_server
        FOREIGN KEY (mcp_server_id) REFERENCES chat_mcp_servers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_mcp_oauth_requests (
    id CHAR(36) NOT NULL,
    state_hash CHAR(64) NOT NULL,
    mcp_server_id BIGINT NOT NULL,
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    encrypted_payload MEDIUMTEXT NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'pending',
    expires_at DATETIME(6) NOT NULL,
    completed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_chat_mcp_oauth_request_state (state_hash),
    KEY idx_chat_mcp_oauth_request_expiry (expires_at, status),
    CONSTRAINT chk_chat_mcp_oauth_request_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'expired')),
    CONSTRAINT fk_chat_mcp_oauth_request_server
        FOREIGN KEY (mcp_server_id) REFERENCES chat_mcp_servers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
