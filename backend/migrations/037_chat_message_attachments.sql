-- 037_chat_message_attachments.sql
-- 채팅 메시지 첨부(이미지) 참조 저장 — 전용 object storage 버킷의 key 목록.
--
-- content/citations/reasoning 과 동일하게 AES-256-GCM(도메인 chat_content)으로 암호화한 JSON 문자열.
-- 형태: [{"key": ..., "mime": ..., "name": ...}]. user 메시지에 채워진다(표시 + 현재턴 vision 재구성용).
-- 기존 행: NULL(첨부 없음). 하위호환.

ALTER TABLE chat_messages
    ADD COLUMN attachments MEDIUMTEXT NULL AFTER reasoning;
