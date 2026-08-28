## Why

The live OpenStack prerequisite detector probes the configured interface with a `public` fallback, but the live test job independently falls back to `internal`. In GitHub Actions this allowed the public network probe to pass and then sent the full live suite to private `172.30.x.x` service endpoints that the hosted runner cannot reach, producing 39 failures after 110 minutes while every deterministic gate passed.

## What Changes

- Use one consistent `public` default for both live detection and live test execution.
- Add an orchestration regression that requires both workflow locations to share that default and rejects the divergent `internal` fallback.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Optional live OpenStack CI runs use the same catalog interface that passed prerequisite detection.

## Impact

- Only `.github/workflows/test.yml` and its orchestration contract test change.
- Explicit `AFTERGLOW_OS_INTERFACE` repository variables still override the default for deployments with runner access to another interface.
- Deterministic unit, contract, and functional gates are unchanged.
