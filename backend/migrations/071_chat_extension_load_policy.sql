-- Control whether an administrator-managed global extension is included in the initial model schema set.
-- Existing extensions become deferred by default to avoid unexpectedly increasing prompt token usage.
ALTER TABLE chat_mcp_servers
    ADD COLUMN IF NOT EXISTS load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand' AFTER is_active;

ALTER TABLE chat_custom_tools
    ADD COLUMN IF NOT EXISTS load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand' AFTER is_active;

-- Normalize installations where an operator had already added the column without a default.
ALTER TABLE chat_mcp_servers
    MODIFY COLUMN load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand';

ALTER TABLE chat_custom_tools
    MODIFY COLUMN load_policy VARCHAR(16) NOT NULL DEFAULT 'on_demand';
