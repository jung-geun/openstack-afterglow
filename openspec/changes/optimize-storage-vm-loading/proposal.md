# Optimize storage and VM loading

## Goal
Remove redundant and invalid file-storage requests, make attachment loading scope-safe, and preload VM configuration choices in the background before their wizard screen opens.

## Scope
- Give each file-storage view one initial-load owner, coalesce automatic/manual refreshes, and pause parent polling behind details.
- Replace the invalid `/api/v1/storage/file-storages` call with `/api/v1/file-storage`; lazily load attachment catalogs by effective project.
- Eliminate duplicate instance-detail mount polling and prevent stale attachment/catalog writes.
- Replace VM-create startup waterfall with idempotent, per-endpoint staged loaders with race-safe admin project switching.
- After boot options settle, preload configuration choices and optional file-storage mounts without delaying the active wizard step.
- Add observable frontend regression tests and update mock transport.

## Non-goals
- Add backend aliases or aggregation endpoints.
- Change normal visible-view polling cadence or the intentional visible-tab refresh.
