-- 029_chat_encrypt_title_model.sql
-- 빌트인 AI 채팅 콘텐츠 암호화 저장 + 제목 요약 모델 지정.
--
-- 1) chat_messages.content / tool_calls, chat_conversations.title 은 이제 AES-256-GCM
--    (도메인 chat_content) 암호문("v3:...")으로 저장된다. 컬럼 자체는 텍스트 타입이면 되지만,
--    tool_calls 는 기존 JSON → MEDIUMTEXT(암호문 문자열), title 은 VARCHAR(255) → TEXT(암호문 길이)로 확장.
--    암호화 이전에 저장된 평문 행은 decrypt_chat_content 가 prefix 없음 → 평문 passthrough 로 하위호환.
-- 2) llm_models.is_title_model: 대화 제목 자동 요약에 쓸 모델 1개를 관리자가 지정(앱 레벨에서 최대 1개 True).

ALTER TABLE chat_messages
    MODIFY COLUMN tool_calls MEDIUMTEXT NULL;

ALTER TABLE chat_conversations
    MODIFY COLUMN title TEXT NULL;

ALTER TABLE llm_models
    ADD COLUMN is_title_model TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active;
