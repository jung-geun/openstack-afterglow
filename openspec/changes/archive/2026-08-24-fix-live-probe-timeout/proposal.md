## Why

The optional live OpenStack detection job runs under `bash -e`. When the Keystone `curl` probe times out, its failing command substitution exits the step immediately with code 28 before the workflow writes `enabled=false`. This turns an unavailable external prerequisite into a deterministic CI failure, violating the layered gate contract.

## What Changes

- Guard the Keystone token request explicitly so transport failures emit a warning, set `enabled=false`, and exit successfully.
- Keep non-201 responses and missing catalog endpoints as the existing non-fatal live verification gaps.
- Add a workflow regression assertion that requires the guarded command substitution.

## Capabilities

### New Capabilities

- `non-fatal-live-prerequisite-detection`: External Keystone timeouts skip only the live layer without blocking deterministic jobs.

### Modified Capabilities

- `layered-development-gates`: The optional live probe now implements the documented failure ownership under `bash -e`.

## Impact

Only the reusable GitHub Actions workflow and its source-level regression test change. Authentication payloads, secrets, application runtime, and test behavior remain unchanged.
