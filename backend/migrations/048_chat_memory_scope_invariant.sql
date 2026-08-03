-- 048_chat_memory_scope_invariant.sql
-- MySQL remains the source of truth for vector candidate hydration. Enforce
-- the namespace invariant before semantic retrieval is enabled.

ALTER TABLE chat_memories
    ADD CONSTRAINT chk_chat_memory_scope
    CHECK (
        (scope = 'account' AND project_id IS NULL AND workspace_id IS NULL)
        OR (scope = 'project' AND project_id IS NOT NULL AND workspace_id IS NULL)
        OR (scope = 'workspace' AND project_id IS NOT NULL AND workspace_id IS NOT NULL)
    ),
    ADD INDEX idx_chat_memories_scope (user_id, project_id, workspace_id, status, is_active);
