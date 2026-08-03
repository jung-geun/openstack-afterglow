-- 030_chat_message_tree.sql
-- 빌트인 AI 채팅 메시지 버전 트리(재생성·분기) + 사용자별 목록 인덱스.
--
-- 1) chat_messages.parent_id: 버전 트리 부모(같은 parent = 재생성 형제 버전). model_name: 형제 버전이
--    어떤 모델로 생성됐는지.
-- 2) chat_conversations.active_leaf_id: 현재 보이는 리프(렌더 경로 = active_leaf → parent 역추적).
--    parent_conversation_id / forked_from_message_id: 분기 출처.
-- 3) 사용자별(프로젝트 무관) 대화 목록 인덱스 (user_id, updated_at).
--
-- 기존 행: parent_id/active_leaf_id 등은 NULL(선형 단일 경로로 취급). 하위호환.

ALTER TABLE chat_messages
    ADD COLUMN parent_id BIGINT NULL AFTER role,
    ADD COLUMN model_name VARCHAR(190) NULL AFTER token_completion,
    ADD INDEX idx_chat_messages_parent (parent_id);

ALTER TABLE chat_conversations
    ADD COLUMN active_leaf_id BIGINT NULL AFTER model_name,
    ADD COLUMN parent_conversation_id CHAR(36) NULL AFTER active_leaf_id,
    ADD COLUMN forked_from_message_id BIGINT NULL AFTER parent_conversation_id,
    ADD INDEX idx_chat_conversations_user_updated (user_id, updated_at);
