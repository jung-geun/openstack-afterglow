CREATE TABLE IF NOT EXISTS vm_cloud_init_snippets (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    name VARCHAR(100) NULL,
    content_encrypted MEDIUMTEXT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_vm_cloud_init_snippets_user_kind_created (user_id, kind, created_at),
    UNIQUE KEY uq_vm_cloud_init_snippet_user_kind_name (user_id, kind, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
