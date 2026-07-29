## Why

Afterglow can consume remote MCP servers from built-in AI chat, but it cannot safely expose its own project-scoped cloud resources to external MCP clients. Browser sessions and `sk-afgl-…` chat keys are deliberately unsuitable for durable delegated OpenStack authority.

## What Changes

- Add an isolated, project-bound delegated-authority system with one-time personal access tokens and Stage 2 OAuth 2.1 grants backed by restricted Keystone application credentials held only by the backend.
- Mount a standards-compliant, stateless Streamable HTTP MCP endpoint at `/api/v1/mcp`, protected by fail-closed grant, scope, epoch, limiter, and ownership checks.
- Define one canonical, consumer-only registry used by external MCP clients and Lumen, with closed schemas, redacted outputs, auditable idempotent mutations, and no admin, secret, shell, binary, or cross-project operations.
- Publish the Stage 1 core VM/storage/network/Trove/Zun catalog and Stage 2 OAuth plus remaining safe consumer cloud services only after the complete authorization, approval, UX, configuration, documentation, and verification gates pass.
- Reuse the registry in Lumen only through durable execution protocol v2, encrypted checkpoints, typed human approvals, and final dispatch-time revalidation.

## Capabilities

### New Capabilities

- Project-bound MCP personal tokens, OAuth 2.1 authorization, and consent management.
- External streamable-HTTP MCP control plane with consumer-safe cloud tools.
- Shared Lumen cloud-control tools with durable v2 approvals.
- Account, consent, and tutorial UI for MCP access and Lumen cloud control.

### Modified Capabilities

- Chat tool runtime, execution protocol, durable run persistence, frontend chat approval handling, configuration/site config, deployment generation, and Korean/English operational documentation.

## Impact

Backend adds MCP APIs, control-plane services, database migrations, service configuration, and shared consumer domain adapters. Frontend adds account MCP management, OAuth consent, tutorial/mock transport, and Lumen approval UI. Existing browser JWT, chat API keys, admin APIs, and remote MCP consumption retain their current authorization boundaries and are explicitly rejected as inbound MCP credentials.
