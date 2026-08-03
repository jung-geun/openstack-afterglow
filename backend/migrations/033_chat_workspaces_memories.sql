-- 032_chat_workspaces_memories.sql
-- Phase C: 채팅 프로젝트(workspace, OpenAI/Claude식 대화 그룹 + 공통 지침) + 사용자 장기 메모리.
-- workspace/instructions·memory/content 는 chat_content 암호문. OpenStack project_id 와 별개 개념.

CREATE TABLE IF NOT EXISTS chat_workspaces (
    id BIGINT NOT NULL AUTO_INCREMENT,
    owner_user_id VARCHAR(64) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NULL,
    instructions MEDIUMTEXT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_chat_workspaces_owner (owner_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chat_memories (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    content MEDIUMTEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_chat_memories_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE chat_conversations
    ADD COLUMN workspace_id BIGINT NULL AFTER forked_from_message_id;
