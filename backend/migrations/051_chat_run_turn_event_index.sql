-- Repair legacy deployments that created message_event_seq as globally unique.
-- The event sequence is scoped to a run; replay needs uniqueness on (run_id, message_event_seq).

SET @has_legacy_global_index := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'chat_run_turns'
      AND INDEX_NAME = 'message_event_seq'
      AND NON_UNIQUE = 0
);
SET @has_canonical_index := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'chat_run_turns'
      AND INDEX_NAME = 'uq_chat_run_turn_message_event'
      AND NON_UNIQUE = 0
);
SET @chat_run_turn_index_sql := CASE
    WHEN @has_legacy_global_index > 0 AND @has_canonical_index > 0
        THEN 'ALTER TABLE chat_run_turns DROP INDEX message_event_seq'
    WHEN @has_legacy_global_index > 0
        THEN 'ALTER TABLE chat_run_turns DROP INDEX message_event_seq, ADD UNIQUE KEY uq_chat_run_turn_message_event (run_id, message_event_seq)'
    WHEN @has_canonical_index = 0
        THEN 'ALTER TABLE chat_run_turns ADD UNIQUE KEY uq_chat_run_turn_message_event (run_id, message_event_seq)'
    ELSE 'SELECT 1'
END;
PREPARE chat_run_turn_index_stmt FROM @chat_run_turn_index_sql;
EXECUTE chat_run_turn_index_stmt;
DEALLOCATE PREPARE chat_run_turn_index_stmt;
