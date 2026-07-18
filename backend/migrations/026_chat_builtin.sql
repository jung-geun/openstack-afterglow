-- 026_chat_builtin.sql
-- 빌트인 AI 채팅 (litellm 라우팅 + LangGraph/MCP + 모델별 가중 크레딧 + 월 쿼터).
-- 기존 외부 LibreChat 임베드를 대체하는 자체 구현의 영속화 계층.
-- 모든 사용자 리소스는 project_id + user_id 를 보유해 소유권 검증(IDOR 방어) 대상이 된다.

-- 관리자가 등록하는 LLM 프로바이더. api_key 는 AES-256-GCM(k3s_kubeconfig_encryption_key,
-- 도메인 llm_provider_key)으로 암호화되어 encrypted_api_key 에 저장된다(평문 저장/응답 금지).
CREATE TABLE IF NOT EXISTS llm_providers (
    id                  BIGINT        AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(100)  NOT NULL,
    api_base            VARCHAR(255)  DEFAULT NULL,
    encrypted_api_key   TEXT          DEFAULT NULL,
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    margin_multiplier   DECIMAL(8,4)  NOT NULL DEFAULT 1.0000,
    created_at          DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    UNIQUE KEY uq_llm_providers_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 노출 모델 카탈로그. input_price/output_price 미지정 시 litellm 내장 단가를 사용한다(override용).
CREATE TABLE IF NOT EXISTS llm_models (
    id            BIGINT         AUTO_INCREMENT PRIMARY KEY,
    provider_id   BIGINT         NOT NULL,
    model_name    VARCHAR(190)   NOT NULL,
    display_name  VARCHAR(150)   DEFAULT NULL,
    is_active     BOOLEAN        NOT NULL DEFAULT TRUE,
    input_price   DECIMAL(20,10) DEFAULT NULL,
    output_price  DECIMAL(20,10) DEFAULT NULL,
    created_at    DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    UNIQUE KEY uq_llm_models_provider_model (provider_id, model_name),
    KEY idx_llm_models_active (is_active),
    CONSTRAINT fk_llm_models_provider
        FOREIGN KEY (provider_id) REFERENCES llm_providers (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 대화 스레드.
CREATE TABLE IF NOT EXISTS chat_conversations (
    id          CHAR(36)     PRIMARY KEY,
    project_id  VARCHAR(64)  NOT NULL,
    user_id     VARCHAR(64)  NOT NULL,
    title       VARCHAR(255) DEFAULT NULL,
    model_name  VARCHAR(190) DEFAULT NULL,
    created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    KEY idx_chat_conversations_owner (project_id, user_id),
    KEY idx_chat_conversations_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 메시지 + LangGraph 메모리 소스.
CREATE TABLE IF NOT EXISTS chat_messages (
    id                BIGINT       AUTO_INCREMENT PRIMARY KEY,
    conversation_id   CHAR(36)     NOT NULL,
    role              VARCHAR(20)  NOT NULL,
    content           MEDIUMTEXT   DEFAULT NULL,
    tool_calls        JSON         DEFAULT NULL,
    token_prompt      INT          NOT NULL DEFAULT 0,
    token_completion  INT          NOT NULL DEFAULT 0,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    KEY idx_chat_messages_conversation (conversation_id, created_at),
    CONSTRAINT fk_chat_messages_conversation
        FOREIGN KEY (conversation_id) REFERENCES chat_conversations (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 사용량/정산 원장. raw_cost 는 litellm 산출 USD, credited_cost 는 마진·환산율 반영 차감 크레딧.
CREATE TABLE IF NOT EXISTS chat_usage_logs (
    id                 BIGINT         AUTO_INCREMENT PRIMARY KEY,
    project_id         VARCHAR(64)    NOT NULL,
    user_id            VARCHAR(64)    NOT NULL,
    conversation_id    CHAR(36)       DEFAULT NULL,
    model_name         VARCHAR(190)   NOT NULL,
    provider           VARCHAR(100)   DEFAULT NULL,
    prompt_tokens      INT            NOT NULL DEFAULT 0,
    completion_tokens  INT            NOT NULL DEFAULT 0,
    raw_cost           DECIMAL(20,10) NOT NULL DEFAULT 0,
    credited_cost      DECIMAL(18,8)  NOT NULL DEFAULT 0,
    source             VARCHAR(10)    NOT NULL DEFAULT 'web',
    api_key_id         BIGINT         DEFAULT NULL,
    created_at         DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    KEY idx_chat_usage_project_created (project_id, created_at),
    KEY idx_chat_usage_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 사용자 지갑: 월 쿼터 상한 + 상용 전환 대비 잔액 필드. quota_period_start 는 월 리셋 기준.
CREATE TABLE IF NOT EXISTS user_wallets (
    user_id                VARCHAR(64)   PRIMARY KEY,
    project_id             VARCHAR(64)   DEFAULT NULL,
    balance_credits        DECIMAL(18,8) NOT NULL DEFAULT 0,
    max_quota_monthly      DECIMAL(18,8) NOT NULL DEFAULT 0,
    used_quota_this_month  DECIMAL(18,8) NOT NULL DEFAULT 0,
    quota_period_start     DATE          DEFAULT NULL,
    is_active              BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at             DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at             DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
