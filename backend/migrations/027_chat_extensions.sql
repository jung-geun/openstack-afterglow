-- 027_chat_extensions.sql
-- 빌트인 AI 채팅 확장: MCP 서버 + 커스텀 HTTP 툴 (관리자 global / 사용자 user 스코프).
-- scope='global'(owner_* NULL)은 관리자가 등록해 전체에 적용, scope='user'는 소유자에게만 적용.
-- 사용자 리소스는 owner_user_id/owner_project_id 로 소유권 검증(IDOR) 대상.

-- MCP 서버 (등록·관리 전용 — 실행은 langchain-mcp-adapters 핀 이동 후 연결)
CREATE TABLE IF NOT EXISTS chat_mcp_servers (
    id                BIGINT       AUTO_INCREMENT PRIMARY KEY,
    scope             VARCHAR(10)  NOT NULL DEFAULT 'user',   -- global | user
    owner_user_id     VARCHAR(64)  DEFAULT NULL,
    owner_project_id  VARCHAR(64)  DEFAULT NULL,
    name              VARCHAR(100) NOT NULL,
    transport         VARCHAR(20)  NOT NULL DEFAULT 'http',   -- http | sse | stdio
    url               VARCHAR(500) DEFAULT NULL,
    command           VARCHAR(500) DEFAULT NULL,
    headers           JSON         DEFAULT NULL,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    KEY idx_chat_mcp_scope (scope),
    KEY idx_chat_mcp_owner (owner_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 커스텀 HTTP 툴 (백엔드가 SSRF 가드하고 대리 호출)
CREATE TABLE IF NOT EXISTS chat_custom_tools (
    id                BIGINT       AUTO_INCREMENT PRIMARY KEY,
    scope             VARCHAR(10)  NOT NULL DEFAULT 'user',
    owner_user_id     VARCHAR(64)  DEFAULT NULL,
    owner_project_id  VARCHAR(64)  DEFAULT NULL,
    name              VARCHAR(64)  NOT NULL,                  -- 툴 이름(영숫자/언더스코어)
    description       VARCHAR(500) NOT NULL,
    method            VARCHAR(10)  NOT NULL DEFAULT 'GET',    -- GET | POST
    url               VARCHAR(500) NOT NULL,
    params_schema     JSON         DEFAULT NULL,              -- LLM 이 채울 인자 JSON schema
    timeout_seconds   INT          NOT NULL DEFAULT 10,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    KEY idx_chat_tool_scope (scope),
    KEY idx_chat_tool_owner (owner_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
