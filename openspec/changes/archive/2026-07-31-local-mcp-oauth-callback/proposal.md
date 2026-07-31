## Why

Remote MCP OAuth used the public `frontend_base_url` for both the provider callback and post-authorization return. In local Docker Compose, the configured production origin (`https://cloud.dmslab.re.kr`) sent Notion authorization away from the local application and reached an endpoint absent from the deployed instance.

## What Changes

- Keep remote-MCP OAuth callback and its initiator cookie on the configured local backend loopback endpoint during development.
- Permit only explicit development HTTP loopback callback URLs; preserve HTTPS-only behavior elsewhere.
- Bind OAuth completion and failure return URLs to the allowlisted browser origin that initiated the flow, with frontend configuration as the safe fallback.
- Add regression coverage for derived and explicit local callback URLs, malformed ports, non-development rejection, and origin-bound completion URLs.

## Capabilities

### New Capabilities

- Local Compose users can complete Notion MCP OAuth without leaving the local application.

### Modified Capabilities

- Remote MCP OAuth callback URL validation and the Secure cookie attribute now align with development loopback URLs.

## Impact

- `backend/app/config.py`, remote MCP OAuth service and route behavior, Docker Compose backend environment, and backend OAuth tests.
- Production and non-development deployments continue to require HTTPS callback URLs.
