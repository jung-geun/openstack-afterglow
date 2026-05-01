-- 007_project_manager_credentials.sql
-- Octavia Ingress App Cred 관리를 위한 프로젝트별 관리 사용자 자격 저장
CREATE TABLE IF NOT EXISTS project_manager_credentials (
    project_id          VARCHAR(64)  NOT NULL,
    user_id             VARCHAR(64)  NOT NULL,
    username            VARCHAR(128) NOT NULL,
    encrypted_password  TEXT         NOT NULL,
    created_at          DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- k3s_clusters에 Octavia Ingress App Credential ID 컬럼 추가
ALTER TABLE k3s_clusters ADD COLUMN app_credential_id VARCHAR(64) DEFAULT NULL;
