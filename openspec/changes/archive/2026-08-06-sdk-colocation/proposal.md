## Why

The Waygate, Drover, and Lumen OpenStack SDK distributions are currently promoted as separate repositories even though each SDK is versioned, tested, and released with its corresponding API service. Keeping the SDK source beside its API server makes a service release atomic and prevents backend dependencies from drifting to a different repository lineage.

## What Changes

- Move each SDK distribution into its owning service tree at `services/<service>/sdk` so a service subtree split contains both its API server and SDK.
- Remove the standalone `services/*-sdk` source trees and stop publishing from separate SDK repositories.
- Repoint Afterglow's immutable backend SDK dependencies and lockfile to each service repository's `sdk` subdirectory at a released commit.
- Run service SDK tests from their colocated paths and update promotion documentation to describe one repository per service.

## Capabilities

### New Capabilities

- Each service repository can build, test, and distribute its server and its OpenStack SDK from a single source tree.

### Modified Capabilities

- Backend SDK dependency resolution uses the owning service repository rather than a standalone SDK repository.

## Impact

- Affects the Waygate, Drover, and Lumen service layouts, service test command, backend dependency metadata and lockfile, and service-promotion documentation.
- SDK distribution names and import packages remain `waygate-sdk`/`waygate_sdk`, `drover-sdk`/`drover_sdk`, and `lumen-sdk`/`lumen_sdk`; existing Python callers keep their imports unchanged.
