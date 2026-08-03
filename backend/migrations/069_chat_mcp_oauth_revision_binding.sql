-- Bind OAuth requests and token bundles to the exact MCP server configuration revision.
-- Legacy user-provided credential injection is deliberately disabled; credentials remain retained
-- at rest for administrator review but are no longer executable by the application.
ALTER TABLE chat_mcp_oauth_connections
    ADD COLUMN IF NOT EXISTS server_config_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER expires_at;

ALTER TABLE chat_mcp_oauth_requests
    ADD COLUMN IF NOT EXISTS server_config_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER encrypted_payload;

UPDATE chat_mcp_oauth_connections AS connection_row
JOIN chat_mcp_servers AS server ON server.id = connection_row.mcp_server_id
SET connection_row.server_config_version = server.config_version;

UPDATE chat_mcp_oauth_requests AS request_row
JOIN chat_mcp_servers AS server ON server.id = request_row.mcp_server_id
SET request_row.server_config_version = server.config_version
WHERE request_row.status IN ('pending', 'processing');

-- Existing encrypted global headers were created through the administrator surface before
-- auth_mode existed; preserve them as explicitly administrator-managed configuration.
UPDATE chat_mcp_servers
SET auth_mode = 'admin',
    config_version = config_version + 1
WHERE scope = 'global'
  AND auth_mode = 'none'
  AND encrypted_headers IS NOT NULL;

-- Unencrypted legacy header blobs are never executed after this migration.
UPDATE chat_mcp_servers
SET is_active = FALSE,
    config_version = config_version + 1
WHERE headers IS NOT NULL
  AND encrypted_headers IS NULL;

-- Old header/template modes depended on user-provided secret variables. They cannot cross this
-- policy boundary; administrators must create an explicit encrypted static-header configuration.
UPDATE chat_mcp_servers
SET is_active = FALSE,
    auth_mode = 'none',
    config_version = config_version + 1
WHERE auth_mode = 'headers'
   OR (scope = 'user' AND (encrypted_headers IS NOT NULL OR headers IS NOT NULL));
