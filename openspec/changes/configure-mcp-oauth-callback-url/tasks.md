## Implementation Tasks

- [x] Add and validate the deployment-owned MCP OAuth callback URL configuration.
- [x] Render the setting into Kubernetes and configuration examples.
- [x] Use the configured callback consistently for OAuth registration, authorization, and token exchange.
- [x] Keep nonce-mismatch requests terminal after transaction commit and cover replay rejection against MariaDB.
- [x] Run focused OAuth route/configuration and MariaDB persistence tests, then rebuild the OAuth services.
