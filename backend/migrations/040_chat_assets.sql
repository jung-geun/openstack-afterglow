-- 039_chat_assets.sql
-- Owned chat asset state machine. Object keys and metadata never expose presigned URLs.

CREATE TABLE chat_assets (
    id CHAR(36) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    object_key VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(127) NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'uploading',
    media_metadata JSON NULL,
    expires_at DATETIME NULL,
    deleting_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_chat_assets_object_key (object_key),
    KEY idx_chat_assets_owner_status (project_id, user_id, status),
    KEY idx_chat_assets_expiry (expires_at)
);

CREATE TABLE chat_message_assets (
    message_id BIGINT NOT NULL,
    asset_id CHAR(36) NOT NULL,
    part_index INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (message_id, asset_id),
    UNIQUE KEY uq_chat_message_assets_part (message_id, part_index),
    CONSTRAINT fk_chat_message_assets_message FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_message_assets_asset FOREIGN KEY (asset_id) REFERENCES chat_assets(id) ON DELETE RESTRICT
);

CREATE TABLE chat_run_assets (
    run_id CHAR(36) NOT NULL,
    asset_id CHAR(36) NOT NULL,
    purpose VARCHAR(30) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, asset_id, purpose),
    CONSTRAINT fk_chat_run_assets_run FOREIGN KEY (run_id) REFERENCES chat_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_run_assets_asset FOREIGN KEY (asset_id) REFERENCES chat_assets(id) ON DELETE RESTRICT
);
