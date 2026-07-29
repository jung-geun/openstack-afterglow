## Why

OAuth providers must receive one exact, browser-reachable redirect URI during dynamic client registration and authorization. Deriving it only from the general public API base makes reverse-proxy and external callback deployments harder to configure and audit.

## What Changes

- Add an optional, deployment-owned MCP OAuth callback URL setting.
- Validate that the configured callback is an absolute HTTPS URL with no credentials or fragment.
- Use the configured URL unchanged for dynamic client registration, authorization requests, and token exchange; retain the existing derived callback as the safe default when unset.
- Keep callback selection server-owned: no user-supplied redirect URI is accepted.
- Record and retain the nonce-mismatch terminal-state/replay regression coverage in this active change.

## Capabilities

### New Capabilities

- Administrators can configure the exact redirect URI used for remote MCP OAuth flows.

### Modified Capabilities

- Remote MCP OAuth uses an explicit configured callback URL when present instead of always deriving `/api/v1/chat/mcp-oauth/callback` from the public API origin.

## Impact

- Backend configuration loading, Kubernetes config rendering, and both example configuration files gain one non-secret application setting.
- Existing deployments remain compatible when the setting is empty.
- OAuth tests cover explicit callback registration and callback-state replay rejection.
