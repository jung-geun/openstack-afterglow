-- 005: 프로젝트별 기본 네트워크 설정 테이블
CREATE TABLE IF NOT EXISTS project_default_networks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL,
    network_id VARCHAR(64) NOT NULL,
    subnet_id VARCHAR(64) DEFAULT NULL,
    router_id VARCHAR(64) DEFAULT NULL,
    auto_created BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) DEFAULT NULL,
    UNIQUE KEY uq_project_default_networks_project_id (project_id),
    KEY ix_project_default_networks_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
