-- 043_chat_skills.sql
-- 빌트인 AI 채팅 스킬(Claude Agent Skills 계열) — MCP/커스텀툴과 같은 확장 체계.
-- scope='global'(owner_* NULL)은 관리자가 등록해 전체에 노출, scope='user'는 소유자에게만 노출.
-- 채팅별로 명시 선택된 스킬만 system 프리앰블에 지침으로 주입한다(opt-in, 실행 아님).
-- instructions 는 프로프라이어터리 프롬프트라 AES-256-GCM(chat_content 도메인)으로 암호화 저장.
-- 사용자 리소스는 owner_user_id/owner_project_id 로 소유권 검증(IDOR) 대상.

CREATE TABLE IF NOT EXISTS chat_skills (
    id                BIGINT       AUTO_INCREMENT PRIMARY KEY,
    scope             VARCHAR(10)  NOT NULL DEFAULT 'user',   -- global | user
    owner_user_id     VARCHAR(64)  DEFAULT NULL,
    owner_project_id  VARCHAR(64)  DEFAULT NULL,
    name              VARCHAR(100) NOT NULL,
    description       VARCHAR(500) DEFAULT NULL,
    instructions      TEXT         NOT NULL,                  -- 암호문(chat_content 도메인)
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    KEY idx_chat_skill_scope (scope),
    KEY idx_chat_skill_owner (owner_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
