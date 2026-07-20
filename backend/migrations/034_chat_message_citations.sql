-- 034_chat_message_citations.sql
-- 채팅 답변 출처(citations) 저장 — Perplexity/Gemini grounding 등이 반환한 근거 URL/제목/스니펫.
--
-- content/tool_calls 와 동일하게 AES-256-GCM(도메인 chat_content)으로 암호화한 JSON 문자열을 보관한다.
-- 형태: [{"url": ..., "title": ..., "snippet": ...}]. 최종 assistant 답변 메시지에만 채워진다.
-- 기존 행: NULL(출처 없음). 하위호환.

ALTER TABLE chat_messages
    ADD COLUMN citations MEDIUMTEXT NULL AFTER tool_calls;
