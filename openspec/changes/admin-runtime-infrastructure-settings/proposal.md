## Why

OpenStack resource selectors currently have split authority between deployment configuration and database `ResourcePolicy` rows. Startup hydration mutates process-local settings and leaves fallback behavior, so API replicas and workers can resolve different infrastructure. Async K3s, Builder, and Waygate work also rereads mutable defaults after creation. Builder retains obsolete global image and SSH state; Notion lacks an environment-scoped master synchronization gate.

## What Changes

- Move all discoverable, non-secret OpenStack selectors to validated database policies and typed runtime settings.
- Snapshot effective selections before asynchronous side effects for K3s, Builder/Union, and Waygate work.
- Introduce an idempotent importer for legacy deployment configuration and remove migrated/dead configuration surfaces after the cutover gate.
- Add grouped admin settings controls and a global Notion synchronization switch.
- Remove process-local settings mutation, TOML selector fallbacks, global Builder images/SSH material, and stale Union-share configuration.

## Capabilities

### New Capabilities
- Database-backed runtime settings for K3s version and Notion synchronization enablement.
- Scoped, validated resource-policy catalogs for OpenStack, Nova/Cinder, Manila, K3s, Builder, and Waygate.
- Immutable resource snapshots for queued or long-running infrastructure operations.
- Idempotent legacy configuration importer with dry-run validation.

### Modified Capabilities
- Instance network/AZ selection, Manila scope selection, K3s provisioning, Builder workflows, Waygate provisioning, and Notion sync all resolve database state exactly and fail closed.
- `/admin/settings` and `/admin/notion` manage the new runtime configuration.

## Impact

Changes span database models/migrations, backend APIs/services/workers, Svelte admin interfaces, deployment configuration generators/templates, documentation, and focused/full verification. Bootstrap OpenStack credentials and operator-authored non-selector settings remain deployment configuration. Dev and production must use separate application databases.
