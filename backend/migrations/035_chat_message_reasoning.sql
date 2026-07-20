-- 035_chat_message_reasoning.sql
-- 채팅 답변의 추론(thinking) 텍스트 저장 — 재로딩 시에도 "어떤 사고를 했는지" 유지.
--
-- content 와 동일하게 AES-256-GCM(도메인 chat_content)으로 암호화한 문자열을 보관한다(JSON 아님, 순수 텍스트).
-- 최종 assistant 답변 메시지에만 채워진다. 기존 행: NULL(추론 없음). 하위호환.

ALTER TABLE chat_messages
    ADD COLUMN reasoning MEDIUMTEXT NULL AFTER citations;
