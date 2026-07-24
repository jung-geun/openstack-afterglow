-- 049_chat_message_history_index.sql
-- Backward history paging seeks by (conversation_id, id), avoiding a full
-- conversation scan when reopening long chats or loading older messages.

ALTER TABLE chat_messages
    ADD INDEX idx_chat_messages_conversation_id (conversation_id, id);
