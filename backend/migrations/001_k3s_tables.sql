-- Union k3s 클러스터 영속화 DDL
-- 실행 방법: mysql -u <user> -p <database> < 001_k3s_tables.sql
-- auto_create_tables = true 설정 시 앱 시작 시 자동 생성됨

CREATE TABLE IF NOT EXISTS k3s_clusters (
    id                   CHAR(36)     NOT NULL,
    project_id           VARCHAR(64)  NOT NULL,
    name                 VARCHAR(63)  NOT NULL,
    status               VARCHAR(20)  NOT NULL DEFAULT 'CREATING',
    status_reason        TEXT,

    -- OpenStack 리소스 ID
    server_vm_id         VARCHAR(64),
    server_flavor_id     VARCHAR(64),
    agent_flavor_id      VARCHAR(64),
    network_id           VARCHAR(64),
    security_group_id    VARCHAR(64),

    -- k3s 정보
    server_ip            VARCHAR(45),
    api_address          VARCHAR(255),
    k3s_version          VARCHAR(32),
    node_token           VARCHAR(512),

    -- SSH / 접근
    key_name             VARCHAR(255),
    ssh_public_key       TEXT,

    -- kubeconfig (AES-256-GCM 암호화 상태로 저장)
    kubeconfig_encrypted TEXT,

    -- 생성자 정보
    created_by_user_id   VARCHAR(64),
    created_by_username  VARCHAR(255),

    -- 설정
    agent_count          INT          NOT NULL DEFAULT 0,

    -- 타임스탬프
    created_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (id),
    INDEX idx_k3s_cluster_project_id (project_id),
    INDEX idx_k3s_cluster_status (status),
    INDEX idx_k3s_cluster_created_by (created_by_user_id),
    INDEX idx_k3s_cluster_project_created (project_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS k3s_agent_vms (
    id          INT          NOT NULL AUTO_INCREMENT,
    cluster_id  CHAR(36)     NOT NULL,
    vm_id       VARCHAR(64)  NOT NULL,
    name        VARCHAR(255),
    status      VARCHAR(20)  NOT NULL DEFAULT 'CREATING',
    created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (id),
    FOREIGN KEY (cluster_id) REFERENCES k3s_clusters(id) ON DELETE CASCADE,
    INDEX idx_k3s_agent_cluster_id (cluster_id),
    INDEX idx_k3s_agent_vm_id (vm_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
