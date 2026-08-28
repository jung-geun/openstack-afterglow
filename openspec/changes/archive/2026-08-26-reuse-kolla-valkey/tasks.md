## Implementation Tasks

### 1. Stock Valkey dependency

- [x] 1.1 Enable stock Kolla Valkey in the plugin globals sample.
- [x] 1.2 Update all five plugin service defaults to use `valkey_server_port`, the Valkey inventory primary, the stock master password, and their existing database indexes.
- [x] 1.3 Add fail-closed prechecks for `enable_valkey`, the Valkey inventory group, and `valkey_master_password` whenever a plugin service is enabled.
- [x] 1.4 Keep Redis-compatible client libraries and `redis://` URL syntax; do not add a plugin Redis role, image, container, volume, or lifecycle.

### 2. Contracts and operator guidance

- [x] 2.1 Add Kolla contract coverage for stock Valkey enablement, current variables, service prechecks, and absence of plugin Redis provisioning.
- [x] 2.2 Update Kolla operator documentation to distinguish stock Valkey deployment from plugin consumption and tagged deployment ordering.

### 3. Verification

- [x] 3.1 Run the focused Kolla contract target.
- [x] 3.2 Render representative role variables and prove the generated cache URLs use Valkey host, port, password, and isolated database indexes.
- [x] 3.3 Run the full repository validation gate.
