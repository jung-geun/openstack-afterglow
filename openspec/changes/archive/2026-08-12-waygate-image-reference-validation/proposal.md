## Why

Waygate deployment accepted an invalid 62-hex worker digest and did not validate the configured immutable `waygate_*_image_ref` values. The precheck instead inspected a legacy `image:tag` value and downgraded failure to a warning, so the first actionable error appeared only when `docker_container` tried to pull the worker during startup.

## What Changes

- Validate enabled Waygate API and worker image references before any deploy, reconfigure, upgrade, pull, database, Keystone, migration, or container mutation.
- Require remote immutable images to use canonical `registry/repository@sha256:<64 lowercase hex>` syntax.
- Inspect each exact configured image reference and fail closed when a manifest is missing or malformed.
- Keep local source-build references on the existing immutable local tag contract.
- Add regression coverage for the 62-character digest failure and exact-reference precheck wiring.

## Capabilities

### New Capabilities

- Fail-fast validation of every enabled Waygate OCI image reference.

### Modified Capabilities

- Waygate precheck validates actual runtime references instead of advisory legacy API tag accessibility.

## Impact

Only the Waygate Kolla role and its deployment-contract tests change. Valid digest-pinned or source-built references retain their current runtime behavior. Invalid references stop before plugin state mutation.
