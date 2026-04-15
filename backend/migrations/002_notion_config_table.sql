-- Notion 연동 설정 영속화 DDL
-- 실행 방법: mysql -u <user> -p <database> < 002_notion_config_table.sql
-- auto_create_tables = true 설정 시 앱 시작 시 자동 생성됨

CREATE TABLE IF NOT EXISTS notion_config (
    id                         INT          NOT NULL AUTO_INCREMENT,

    -- Notion API key (AES-256-GCM 암호화)
    api_key_encrypted          TEXT         NOT NULL,

    -- 데이터베이스 ID
    database_id                VARCHAR(64)  NOT NULL DEFAULT '',
    users_database_id          VARCHAR(64),
    hypervisors_database_id    VARCHAR(64),
    gpu_spec_database_id       VARCHAR(64),

    -- 동기화 설정
    enabled                    TINYINT(1)   NOT NULL DEFAULT 0,
    interval_minutes           INT          NOT NULL DEFAULT 5,

    -- 마지막 동기화 시각
    last_sync                  DATETIME(6),
    hypervisors_last_sync      DATETIME(6),
    gpu_spec_last_sync         DATETIME(6),

    -- 타임스탬프
    created_at                 DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                 DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
