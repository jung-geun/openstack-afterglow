-- 046_chat_run_replay_cursors.sql
-- Persist journal identities for per-turn and tool-segment replay. A completed
-- boundary can then reconstruct state without emitting duplicate SSE events.

ALTER TABLE chat_run_turns
    ADD COLUMN completion_event_seq BIGINT NULL AFTER message_event_seq;

ALTER TABLE chat_run_segments
    ADD COLUMN started_event_seq BIGINT NULL AFTER usage_payload,
    ADD COLUMN completed_event_seq BIGINT NULL AFTER started_event_seq;
