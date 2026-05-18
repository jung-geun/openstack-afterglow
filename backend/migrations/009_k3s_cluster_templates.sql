-- k3s 클러스터 템플릿 DDL
-- 실행 방법: mysql -u <user> -p <database> < 009_k3s_cluster_templates.sql
-- auto_create_tables = true 설정 시 앱 시작 시 자동 생성됨

CREATE TABLE IF NOT EXISTS k3s_cluster_templates (
    id                       CHAR(36)     NOT NULL,
    name                     VARCHAR(63)  NOT NULL,
    description              TEXT,
    k3s_version              VARCHAR(32),
    default_node_count       INT          NOT NULL DEFAULT 1,
    default_agent_flavor_id  VARCHAR(64),
    default_image_id         VARCHAR(64),
    plugins_enabled          JSON,
    os_type                  VARCHAR(10)  NOT NULL DEFAULT 'ubuntu',
    public_visible           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by               VARCHAR(64),
    created_at               DATETIME(6)  NOT NULL,
    updated_at               DATETIME(6)  NOT NULL,
    deleted_at               DATETIME(6),

    PRIMARY KEY (id),
    INDEX idx_k3s_cluster_templates_name (name),
    INDEX idx_k3s_cluster_templates_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- k3s_clusters 에 template 추적 컬럼 추가
ALTER TABLE k3s_clusters
    ADD COLUMN IF NOT EXISTS template_id       CHAR(36) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS template_snapshot JSON     DEFAULT NULL;
