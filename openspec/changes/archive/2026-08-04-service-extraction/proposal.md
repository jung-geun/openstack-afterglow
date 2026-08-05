## Why

Afterglow currently embeds the Drover K3s control plane, Waygate WireGuard control plane, and Lumen chat/LLM control plane in one FastAPI deployment. This couples release cadence, data ownership, worker lifecycle, and OpenStack integration, while duplicated tests increase maintenance cost without increasing coverage.

## What Changes

- Consolidate exact and strictly weaker duplicate backend/frontend tests before service extraction.
- Extract shared encryption and SSH-key validation boundaries.
- Add an Afterglow BFF proxy that preserves existing browser API paths and makes upstream unavailability explicit.
- Extract Waygate, Drover, and Lumen as independent distributions under `services/`, each with its own FastAPI API, worker, database migrations, Python SDK, OCI images, and Kolla Ansible role.
- Register each service in the Keystone service catalog and expose it through an openstacksdk extension.
- Migrate service-owned database and Redis state during maintenance windows, then remove ownership from Afterglow.
- Keep Afterglow as the dashboard/BFF and preserve baked guest callback contracts.

## Capabilities

### New Capabilities

- Independently deployable Waygate, Drover, and Lumen services.
- Catalog-discovered `waygate-sdk`, `drover-sdk`, and `lumen-sdk` clients.
- Durable Waygate and Drover job processing.
- Explicit service-availability reporting in dashboard aggregation.
- Service-specific container images, Compose services, migration runners, and Kolla roles.

### Modified Capabilities

- Existing `/api/v1/waygate`, `/api/v1/k3s`, and `/api/v1/chat` browser routes become Afterglow BFF proxies without frontend path changes.
- The legacy `/api/k3s/callback` and baked Waygate agent URLs remain permanently supported.
- Lumen consumes Afterglow's MCP control plane remotely rather than importing it directly.
- Service-owned tables, Redis state, crypto domains, and runtime settings move to their owning distributions.

## Impact

The change touches backend routing, service ownership, migrations, tests, Docker/Compose, Kolla deployment, and SDK packaging. Cutover requires maintenance windows and verified row-count, encrypted-data, durable-worker, proxy, catalog, and legacy callback checks. Existing public browser paths remain stable; unavailable services return explicit HTTP 503 responses instead of misleading empty data.
