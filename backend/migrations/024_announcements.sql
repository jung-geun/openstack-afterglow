-- 024_announcements.sql
-- 관리자 공지(announcement) 및 유저별 읽음 상태.
-- target_type: 'all' | 'project' | 'user'. target_id는 target_type='all'일 때 NULL.

CREATE TABLE IF NOT EXISTS announcements (
    id                   BIGINT       AUTO_INCREMENT PRIMARY KEY,
    created_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_user_id   VARCHAR(64)  NOT NULL,
    created_by_username  VARCHAR(255) NOT NULL,
    title                VARCHAR(200) NOT NULL,
    body                 TEXT         NOT NULL,
    severity             VARCHAR(16)  NOT NULL DEFAULT 'info',
    target_type          VARCHAR(16)  NOT NULL,
    target_id            VARCHAR(64)  DEFAULT NULL,
    starts_at            DATETIME(6)  DEFAULT NULL,
    ends_at              DATETIME(6)  DEFAULT NULL,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,

    KEY idx_announcements_active_target (is_active, target_type, target_id),
    KEY idx_announcements_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS announcement_reads (
    announcement_id  BIGINT       NOT NULL,
    user_id          VARCHAR(64)  NOT NULL,
    read_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (announcement_id, user_id),
    CONSTRAINT fk_announcement_reads_announcement
        FOREIGN KEY (announcement_id) REFERENCES announcements (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
