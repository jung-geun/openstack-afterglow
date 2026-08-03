-- 031_chat_agents.sql
-- 사용자 정의 에이전트 — 프롬프트(instructions) + 모델 + 파라미터 + MCP/툴 묶음.
-- visibility='public' 은 허브에서 검색·복제 가능(수정은 소유자만). instructions 는 chat_content 암호문.

CREATE TABLE IF NOT EXISTS chat_agents (
    id BIGINT NOT NULL AUTO_INCREMENT,
    owner_user_id VARCHAR(64) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NULL,
    avatar VARCHAR(500) NULL,
    instructions MEDIUMTEXT NULL,
    model_name VARCHAR(190) NULL,
    params JSON NULL,
    mcp_ids JSON NULL,
    tool_ids JSON NULL,
    visibility VARCHAR(10) NOT NULL DEFAULT 'private',
    cloned_from_id BIGINT NULL,
    clone_count INT NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_chat_agents_owner (owner_user_id),
    INDEX idx_chat_agents_visibility (visibility)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
