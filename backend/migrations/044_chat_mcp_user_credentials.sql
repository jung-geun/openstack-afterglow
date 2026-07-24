-- 044_chat_mcp_user_credentials.sql
-- 원격 MCP 서버의 "사용자별 인증 요구사항" — Notion/Gmail 등 개별 사용자 자격증명이 필요한 서버.
--
-- 관리자는 서버 등록 시 공용 시크릿을 주입하지 않고 auth_requirements 로 "요구사항"만 선언한다
-- (예: [{"key":"Authorization","label":"Notion Integration Token"}]). auth_requirements 는
-- 비밀이 아니라 어떤 헤더를 사용자가 채워야 하는지 알리는 메타데이터라 평문 JSON.
--
-- 각 사용자는 자신의 값을 chat_mcp_credentials 에 채운다(값은 AES-256-GCM(llm_provider_key 도메인)
-- 암호화). 실행 시 서버 기본 헤더 위에 사용자 값을 병합하고, 요구사항 미충족 서버는 노출하지 않는다.

ALTER TABLE chat_mcp_servers
    ADD COLUMN auth_requirements JSON NULL AFTER encrypted_headers;

CREATE TABLE IF NOT EXISTS chat_mcp_credentials (
    id                BIGINT       AUTO_INCREMENT PRIMARY KEY,
    mcp_server_id     BIGINT       NOT NULL,
    owner_user_id     VARCHAR(64)  NOT NULL,
    owner_project_id  VARCHAR(64)  NOT NULL,
    encrypted_values  TEXT         NOT NULL,               -- 암호문 JSON {header_key: value}
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    UNIQUE KEY uq_chat_mcp_cred (mcp_server_id, owner_user_id, owner_project_id),
    KEY idx_chat_mcp_cred_owner (owner_user_id, owner_project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
