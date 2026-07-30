-- Explicit external-MCP auth modes, administrator OAuth client fallback, and user secret-variable header templates.
ALTER TABLE chat_mcp_servers
    ADD COLUMN IF NOT EXISTS auth_header_templates JSON NULL AFTER auth_requirements,
    ADD COLUMN IF NOT EXISTS oauth_scopes JSON NULL AFTER auth_mode,
    ADD COLUMN IF NOT EXISTS oauth_client_id VARCHAR(512) NULL AFTER oauth_scopes,
    ADD COLUMN IF NOT EXISTS encrypted_oauth_client_secret MEDIUMTEXT NULL AFTER oauth_client_id;
