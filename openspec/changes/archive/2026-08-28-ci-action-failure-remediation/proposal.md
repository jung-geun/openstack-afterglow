## Why

PR #60 and its `main` merge left failed GitHub Actions records even though the exact `v1.17.1` tag workflow later passed. The failures must be separated into real workflow defects, external OpenStack transients, and obsolete historical runs so current CI is trustworthy without suppressing genuine auth or integration failures.

## What Changes

- Audit recent failed and action-required Actions runs and retain evidence for each current failure class.
- Prevent Copilot-generated pull-request review events from producing spurious Claude Code workflow failures while preserving explicit `@claude` invocation from the PR conversation.
- Rerun current transient OpenStack failures instead of weakening fail-closed live integration tests.
- Verify the release, Docker, Helm, and current branch workflows after remediation.

## Capabilities

### New Capabilities

- Current Actions failures are classified and remediated with exact run evidence.

### Modified Capabilities

- Claude Code invocation accepts explicit repository-user requests without reacting to automated Copilot review events.
- Transient live OpenStack failures remain visible and fail closed, but current runs are rerun after infrastructure recovery.

## Impact

The change is limited to GitHub Actions trigger behavior, OpenSpec records, and rerunning existing workflows. Application runtime behavior and authentication semantics remain unchanged.
