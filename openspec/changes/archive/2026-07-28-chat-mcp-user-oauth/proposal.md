## Why

Remote MCP configuration can only accept static headers today. Notion's hosted MCP requires an interactive OAuth connection per user, so an unauthenticated Notion server is repeatedly probed and cannot be used safely.

## What Changes

- Classify the hosted Notion MCP endpoint as OAuth-required automatically and persist per-user, per-project OAuth connections separately from static header credentials.
- Add an OAuth 2.1 authorization-code + PKCE flow with discovery, dynamic client registration, encrypted token storage, refresh, state binding, and a callback that never exposes tokens to the browser.
- Show each user's connection state in chat extension settings, provide connect/reconnect/disconnect actions, and omit disconnected OAuth MCP servers from tool discovery.

## Security Constraints

- All discovery, registration, and token requests cross the existing DNS-pinned, HTTPS-only SSRF boundary.
- OAuth state and PKCE verifier are server-held, short-lived, single-use, and bound to the initiating user/project/server.
- Tokens and dynamic client secrets remain AES-GCM encrypted at rest and are only decrypted on the chat worker execution path.
