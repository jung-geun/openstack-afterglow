## Implementation Tasks

- [x] Add migration 070 and the project-owned, lease-fenced `PalimpsestImageExport` ORM model with immutable Glance source fingerprints, deduplication, soft deletion, and persistent result metadata.
- [x] Extend the hub store format map and implement bounded symlink-safe atomic promotion, deferred reference-aware blob GC, and all-six-format media/filename handling.
- [x] Implement the durable export service and worker: requester validation, current Glance authorization recheck, streamed hash-verified download, source backing-reference rejection, space measurement, bounded qemu conversion, retries, heartbeat fencing, and scratch cleanup.
- [x] Add project-isolated export list/detail/delete/blob routes, one-use Redis browser tickets, shared Range responses, and regression coverage for authorization, leases, conversion failures, downloads, and GC.
- [x] Add the standard-library `palimpsest image list` and verified one-command `image pull`, preserving all existing CLI commands and covering parser/poll/partial-file contracts.
- [x] Add the image detail export UI with existing design primitives, six status mappings, stale-safe polling, and explicit streamed download action with component tests.
- [x] Package and deploy the worker with `qemu-utils` and shared Compose/Kubernetes storage; validate focused tests, DB behavior, container conversion, manifests, live CLI pull, browser flow, then full test/lint gates.
