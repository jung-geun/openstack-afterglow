-- 008_activity_log.sql
-- 사용자 활동 로그 (compute / storage / network / k3s / container / file_storage / library)
CREATE TABLE IF NOT EXISTS activity_logs (
    id              BIGINT       AUTO_INCREMENT PRIMARY KEY,
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    project_id      VARCHAR(64)  NOT NULL,
    user_id         VARCHAR(64)  NOT NULL,
    username        VARCHAR(255) NOT NULL,
    resource_type   VARCHAR(32)  NOT NULL,
    resource_id     VARCHAR(128) DEFAULT NULL,
    resource_name   VARCHAR(255) DEFAULT NULL,
    action          VARCHAR(48)  NOT NULL,
    status          VARCHAR(16)  NOT NULL,
    error_message   TEXT         DEFAULT NULL,
    extra           JSON         DEFAULT NULL,

    KEY idx_activity_project_created (project_id, created_at),
    KEY idx_activity_user_created (user_id, created_at),
    KEY idx_activity_resource (resource_type, resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
