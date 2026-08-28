## Why

Kolla supplies a legacy Nova availability-zone selector but did not reconcile it into authoritative `resource_policies`. Missing compute and Cinder placement rows prevent instance creation. The deployed API must fail closed with a safe 503 while Kolla idempotently seeds missing rows.

## What Changes

- Run the existing validated runtime-infrastructure importer in a one-shot Afterglow backend container during deploy, reconfigure, and upgrade.
- Preserve operator-selected existing rows; validate legacy resources and fail nonzero on unavailable values or unresolved snapshots.
- Add focused regression coverage for ordered missing placement policies and Kolla lifecycle/container contracts.

## Capabilities

### New Capabilities

- Kolla automatically reconciles declared runtime placement defaults into missing authoritative policy rows.

### Modified Capabilities

- Afterglow Kolla lifecycle tasks run policy seeding after runtime configuration and before service availability.

## Impact

Changes are confined to the custom Afterglow Kolla role and regression tests. No stock Kolla globals, passwords, playbooks, or existing policy selections are modified.
