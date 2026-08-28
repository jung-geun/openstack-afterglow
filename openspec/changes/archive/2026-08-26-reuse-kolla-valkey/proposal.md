## Why

Current Kolla Ansible releases provide Valkey as the stock Redis-protocol service. The plugin already points its application cache URLs at the Valkey inventory group, but the contract is incomplete: the sample does not enable stock Valkey, roles do not fail closed when it is disabled, and defaults still reference the legacy `redis_port` variable. This can leave operators believing the plugin will create or use a separate Redis service.

## What Changes

- Declare stock `enable_valkey: yes` in the plugin Kolla globals sample.
- Require enabled plugin services to have Kolla Valkey enabled, a non-empty Valkey inventory group, and the stock master password.
- Derive every plugin cache URL from Kolla's first Valkey controller API address, `valkey_server_port`, and `valkey_master_password`, retaining the `redis://` scheme and existing per-service database indexes.
- Add contracts proving no plugin-owned Redis role, container, image, or service is introduced.
- Document that Kolla deploys Valkey; the plugin only consumes it and therefore requires Valkey to be deployed before plugin-only tagged lifecycle commands.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Kolla deployments use the stock Valkey service as the sole Redis-protocol cache for Afterglow, Waygate, Drover, Lumen, and Palimpsest.

## Impact

Development Docker Compose remains unchanged. Application libraries continue using Redis-compatible clients and `redis://` URLs. The Kolla plugin does not manage an independent Redis lifecycle and fails prechecks instead of silently targeting an absent cache. Direct-primary connectivity remains explicit; adopting Kolla's Sentinel connection string requires separate client support across every extracted service.
