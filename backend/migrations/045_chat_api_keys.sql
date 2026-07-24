-- 045_chat_api_keys.sql
-- 빌트인 AI 채팅 외부 API 키 — 사용자가 OpenAI/Anthropic 호환 엔드포인트(/v1/*)에 접속할 때 사용.
--
-- 키 평문은 발급 시 1회만 반환하고 저장하지 않는다. DB엔 SHA-256 해시(key_hash)와 표시용 prefix만 저장.
-- 인증 시 요청 키를 sha256 해시해 key_hash 로 조회 후 hmac.compare_digest 로 타이밍 안전 비교한다.
-- 사용량은 chat_usage_logs.api_key_id(이미 존재) 로 이 테이블 id 를 참조한다(FK 없음 — 폐기 후에도 원장 보존).

CREATE TABLE IF NOT EXISTS chat_api_keys (
    id                BIGINT       AUTO_INCREMENT PRIMARY KEY,
    owner_user_id     VARCHAR(64)  NOT NULL,
    owner_project_id  VARCHAR(64)  NOT NULL,
    name              VARCHAR(100) NOT NULL DEFAULT '',       -- 사용자 지정 라벨
    key_prefix        VARCHAR(24)  NOT NULL,                  -- 표시용(예: sk-afgl-AbCd) — 시크릿 아님
    key_hash          CHAR(64)     NOT NULL,                  -- SHA-256(전체 키) hex
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    last_used_at      DATETIME(6)  DEFAULT NULL,
    revoked_at        DATETIME(6)  DEFAULT NULL,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    UNIQUE KEY uq_chat_api_keys_hash (key_hash),
    KEY idx_chat_api_keys_owner (owner_user_id, owner_project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
