-- 055_chat_extension_packages.sql
-- Project-scoped declarative commands and immutable extension packages. No executable hooks.

ALTER TABLE chat_skills
    ADD COLUMN project_id VARCHAR(64) NULL AFTER owner_project_id,
    ADD COLUMN slug VARCHAR(100) NULL AFTER name,
    ADD COLUMN argument_hint VARCHAR(500) NULL AFTER description,
    ADD COLUMN user_invocable BOOLEAN NOT NULL DEFAULT TRUE AFTER argument_hint,
    ADD COLUMN model_invocable BOOLEAN NOT NULL DEFAULT FALSE AFTER user_invocable,
    ADD COLUMN content_hash CHAR(64) NULL AFTER instructions,
    ADD COLUMN source_package_id CHAR(36) NULL AFTER content_hash,
    ADD COLUMN source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY idx_chat_skills_project (project_id),
    ADD UNIQUE KEY uq_chat_skills_project_slug (project_id, slug);
UPDATE chat_skills SET project_id = owner_project_id WHERE project_id IS NULL;

ALTER TABLE chat_agents
    ADD COLUMN project_id VARCHAR(64) NULL AFTER owner_user_id,
    ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'general' AFTER visibility,
    ADD COLUMN execution_policy JSON NULL AFTER role,
    ADD COLUMN delegable_agent_ids JSON NULL AFTER execution_policy,
    ADD COLUMN skill_ids JSON NULL AFTER tool_ids,
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER clone_count,
    ADD COLUMN content_hash CHAR(64) NULL AFTER instructions,
    ADD COLUMN source_package_id CHAR(36) NULL AFTER content_hash,
    ADD COLUMN source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY idx_chat_agents_project (project_id),
    ADD KEY idx_chat_agents_project_active (project_id, is_active);

ALTER TABLE chat_custom_tools
    ADD COLUMN project_id VARCHAR(64) NULL AFTER owner_project_id,
    ADD COLUMN effect VARCHAR(30) NOT NULL DEFAULT 'external_mutation' AFTER timeout_seconds,
    ADD COLUMN config_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER effect,
    ADD COLUMN source_package_id CHAR(36) NULL AFTER config_version,
    ADD COLUMN source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY idx_chat_custom_tools_project (project_id);
UPDATE chat_custom_tools SET project_id = owner_project_id WHERE project_id IS NULL;

ALTER TABLE chat_mcp_servers
    ADD COLUMN project_id VARCHAR(64) NULL AFTER owner_project_id,
    ADD COLUMN tool_effect_overrides JSON NULL AFTER auth_requirements,
    ADD COLUMN config_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER tool_effect_overrides,
    ADD COLUMN source_package_id CHAR(36) NULL AFTER config_version,
    ADD COLUMN source_package_version VARCHAR(64) NULL AFTER source_package_id,
    ADD COLUMN managed_by_package BOOLEAN NOT NULL DEFAULT FALSE AFTER source_package_version,
    ADD KEY idx_chat_mcp_servers_project (project_id);
UPDATE chat_mcp_servers SET project_id = owner_project_id WHERE project_id IS NULL;

ALTER TABLE chat_mcp_credentials
    ADD COLUMN credential_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER encrypted_values,
    ADD COLUMN revoked_at DATETIME NULL AFTER credential_version;

CREATE TABLE chat_commands (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id VARCHAR(64) NOT NULL,
    project_id VARCHAR(64) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    prompt_template_ciphertext MEDIUMTEXT NOT NULL,
    argument_hint VARCHAR(500) NULL,
    agent_id BIGINT NULL,
    skill_ids JSON NULL,
    execution_mode VARCHAR(10) NOT NULL DEFAULT 'chat',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    content_hash CHAR(64) NOT NULL,
    source_package_id CHAR(36) NULL,
    source_package_version VARCHAR(64) NULL,
    managed_by_package BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_commands_project_slug (project_id, slug),
    KEY idx_chat_commands_owner_project (owner_user_id, project_id, is_active),
    CONSTRAINT fk_chat_commands_agent FOREIGN KEY (agent_id) REFERENCES chat_agents(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_extension_packages (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(64) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    manifest_ciphertext MEDIUMTEXT NOT NULL,
    manifest_hash CHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by_user_id VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_extension_packages_name_version (name, version),
    KEY idx_chat_extension_packages_status (status, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_extension_package_installs (
    id CHAR(36) PRIMARY KEY,
    package_id CHAR(36) NOT NULL,
    package_name VARCHAR(100) NOT NULL,
    owner_user_id VARCHAR(64) NOT NULL,
    owner_project_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'installing',
    installed_version VARCHAR(64) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_extension_install_request (owner_user_id, owner_project_id, request_fingerprint),
    UNIQUE KEY uq_chat_extension_install_project_name (owner_user_id, owner_project_id, package_name),
    KEY idx_chat_extension_installs_owner_status (owner_user_id, owner_project_id, status),
    CONSTRAINT fk_chat_extension_installs_package FOREIGN KEY (package_id) REFERENCES chat_extension_packages(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_extension_package_components (
    install_id CHAR(36) NOT NULL,
    component_type VARCHAR(30) NOT NULL,
    component_ref VARCHAR(100) NOT NULL,
    materialized_id BIGINT NULL,
    content_hash CHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (install_id, component_type, component_ref),
    CONSTRAINT fk_chat_extension_components_install FOREIGN KEY (install_id) REFERENCES chat_extension_package_installs(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
