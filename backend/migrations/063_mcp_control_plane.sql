-- Project-bound delegated authority and inbound MCP control-plane persistence.
-- Every table is additive and idempotent for MariaDB 10.11+.

CREATE TABLE IF NOT EXISTS mcp_owner_locks (
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    lumen_selection_generation BIGINT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (owner_user_id, owner_project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_delegated_grants (
    id CHAR(36) NOT NULL,
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    upstream_credential_name VARCHAR(128) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    source VARCHAR(20) NOT NULL,
    access_level VARCHAR(10) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    application_credential_id VARCHAR(128) NULL,
    credential_ciphertext MEDIUMTEXT NULL,
    credential_epoch BIGINT UNSIGNED NOT NULL DEFAULT 1,
    expires_at DATETIME(6) NOT NULL,
    issued_at DATETIME(6) NULL,
    revoked_at DATETIME(6) NULL,
    cleanup_pending BOOLEAN NOT NULL DEFAULT FALSE,
    cleanup_last_attempt_at DATETIME(6) NULL,
    orphan_recovery_after DATETIME(6) NULL,
    orphan_recovery_nonce CHAR(36) NULL,
    last_used_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_grants_upstream_name (upstream_credential_name),
    KEY idx_mcp_grants_owner_status (owner_user_id, owner_project_id, status),
    KEY idx_mcp_grants_expiry (expires_at, status),
    CONSTRAINT chk_mcp_grant_source CHECK (source IN ('personal_token', 'oauth')),
    CONSTRAINT chk_mcp_grant_access CHECK (access_level IN ('read', 'manage')),
    CONSTRAINT chk_mcp_grant_status CHECK (status IN ('pending', 'active', 'revoked', 'expired'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_personal_tokens (
    id CHAR(36) NOT NULL,
    grant_id CHAR(36) NOT NULL,
    visible_prefix VARCHAR(32) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    issued_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_used_at DATETIME(6) NULL,
    revoked_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_personal_tokens_grant (grant_id),
    UNIQUE KEY uq_mcp_personal_tokens_hash (token_hash),
    KEY idx_mcp_personal_tokens_grant (grant_id),
    CONSTRAINT fk_mcp_personal_tokens_grant FOREIGN KEY (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_lumen_selections (
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    grant_id CHAR(36) NOT NULL,
    selected_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (owner_user_id, owner_project_id),
    CONSTRAINT fk_mcp_lumen_selection_grant FOREIGN KEY (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
    id CHAR(36) NOT NULL,
    client_id VARCHAR(512) NOT NULL,
    metadata JSON NOT NULL,
    redirect_uris JSON NOT NULL,
    client_id_issued_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at DATETIME(6) NULL,
    last_used_at DATETIME(6) NULL,
    revoked_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_oauth_clients_client_id (client_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_oauth_authorization_requests (
    id CHAR(36) NOT NULL,
    ticket_hash CHAR(64) NOT NULL,
    client_id VARCHAR(512) NOT NULL,
    client_fingerprint CHAR(64) NOT NULL,
    redirect_uri VARCHAR(2048) NOT NULL,
    resource VARCHAR(2048) NOT NULL,
    scopes JSON NOT NULL,
    code_challenge VARCHAR(256) NOT NULL,
    state VARCHAR(2048) NULL,
    owner_user_id VARCHAR(64) NULL,
    owner_project_id VARCHAR(64) NULL,
    grant_deadline DATETIME(6) NULL,
    grant_id CHAR(36) NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'pending',
    expires_at DATETIME(6) NOT NULL,
    used_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_oauth_requests_ticket_hash (ticket_hash),
    KEY idx_mcp_oauth_requests_owner (owner_user_id, owner_project_id, status),
    KEY idx_mcp_oauth_requests_expiry (expires_at, status),
    CONSTRAINT chk_mcp_oauth_request_status CHECK (status IN ('pending', 'approved', 'denied', 'expired')),
    CONSTRAINT fk_mcp_oauth_requests_grant FOREIGN KEY (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_oauth_codes (
    id CHAR(36) NOT NULL,
    code_hash CHAR(64) NOT NULL,
    grant_id CHAR(36) NOT NULL,
    client_id VARCHAR(512) NOT NULL,
    redirect_uri VARCHAR(2048) NOT NULL,
    resource VARCHAR(2048) NOT NULL,
    scopes JSON NOT NULL,
    code_challenge VARCHAR(256) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    used_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_oauth_codes_hash (code_hash),
    CONSTRAINT fk_mcp_oauth_codes_grant FOREIGN KEY (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_oauth_token_families (
    id CHAR(36) NOT NULL,
    grant_id CHAR(36) NOT NULL,
    generation BIGINT UNSIGNED NOT NULL DEFAULT 1,
    revoked_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_oauth_token_families_grant (grant_id),
    CONSTRAINT fk_mcp_oauth_token_families_grant FOREIGN KEY (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_oauth_tokens (
    id CHAR(36) NOT NULL,
    family_id CHAR(36) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    token_type VARCHAR(10) NOT NULL,
    resource VARCHAR(2048) NOT NULL,
    scopes JSON NOT NULL,
    generation BIGINT UNSIGNED NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    issued_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    used_at DATETIME(6) NULL,
    rotated_at DATETIME(6) NULL,
    revoked_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_oauth_tokens_hash (token_hash),
    KEY idx_mcp_oauth_tokens_family (family_id, token_type, generation),
    KEY idx_mcp_oauth_tokens_expiry (expires_at, token_type),
    CONSTRAINT chk_mcp_oauth_token_type CHECK (token_type IN ('access', 'refresh')),
    CONSTRAINT fk_mcp_oauth_tokens_family FOREIGN KEY (family_id) REFERENCES mcp_oauth_token_families(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mcp_tool_invocations (
    id CHAR(36) NOT NULL,
    grant_id CHAR(36) NOT NULL,
    source VARCHAR(10) NOT NULL,
    tool_name VARCHAR(128) NOT NULL,
    idempotency_key VARCHAR(128) NULL,
    arguments_hash CHAR(64) NOT NULL,
    registry_version VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'claimed',
    lease_expires_at DATETIME(6) NULL,
    dispatch_authorized_at DATETIME(6) NULL,
    sent_at DATETIME(6) NULL,
    result MEDIUMTEXT NULL,
    error TEXT NULL,
    resource_ref VARCHAR(512) NULL,
    operation_ref VARCHAR(512) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_mcp_invocation_claim (grant_id, source, tool_name, idempotency_key),
    KEY idx_mcp_invocations_grant_created (grant_id, created_at),
    CONSTRAINT chk_mcp_invocation_source CHECK (source IN ('mcp', 'lumen')),
    CONSTRAINT chk_mcp_invocation_status CHECK (status IN ('claimed', 'dispatch_authorized', 'succeeded', 'failed', 'unknown')),
    CONSTRAINT fk_mcp_invocations_grant FOREIGN KEY (grant_id) REFERENCES mcp_delegated_grants(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
