-- 041_chat_message_parts_contract.sql
-- A3 canonical-read contract. Apply only after A2 verifies every existing row has encrypted,
-- valid canonical parts and a matching legacy text projection. Legacy columns intentionally remain.

ALTER TABLE chat_messages
    MODIFY COLUMN parts MEDIUMTEXT NOT NULL,
    MODIFY COLUMN parts_version INT NOT NULL DEFAULT 1,
    ADD CONSTRAINT chk_chat_messages_status CHECK (status IN ('streaming', 'complete', 'failed', 'canceled'));

ALTER TABLE chat_conversations
    ADD CONSTRAINT chk_chat_conversations_lifecycle CHECK (lifecycle_status IN ('active', 'deleting'));
