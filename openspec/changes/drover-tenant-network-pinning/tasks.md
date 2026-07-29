## Implementation

- [x] Thread required `primary_network_id` through all K3s renderers and provisioning callers.
- [x] Add the shared first-boot primary-network pin script with metadata resolution, validation, locking, atomic persistence, and NIC replay.
- [x] Embed and invoke the pin in Ubuntu and FCOS server/agent userdata; remove route-based address discovery and CLI `--node-ip`.
- [x] Make Ubuntu and FCOS secondary NIC activation route-neutral with bounded pin waits and safe locking.
- [x] Enforce primary-aware K3s interface attach/detach API invariants and audit rejected branches.
- [x] Expose `is_primary` and update the K3s networks card controls.
- [x] Add backend pinning and API regression tests; update renderer tests for the drop-in contract.
- [x] Add frontend networks-card tests and register the K3s target without changing the visual-debt baseline.

## Verification

- [x] Run all focused backend/frontend targets from the approved plan.
- [ ] Run `npm run test:all` and `npm run lint:backend` successfully.
- [x] Complete the available live OpenStack smoke proof or record the exact unavailable prerequisite.
- [ ] Archive with `openspec archive drover-tenant-network-pinning --skip-specs --yes` after verification.

Live smoke blocker: the running dev deployment is reachable and authenticated, but
`/api/v1/admin/resource-policies` reports `k3s.server_image`, `k3s.fcos_image`,
`k3s.server_flavor`, and `k3s.default_agent_flavor` as unset. The deployment therefore
cannot create the fresh Ubuntu/FCOS cluster required for the smoke sequence.

Full-gate note: focused K3s targets, `tests/integration` (199 passed, 13 skipped),
and the frontend suite (850 passed) pass. `npm run test:all` stops at 11 unrelated
chat/MCP/migration baseline failures; `npm run lint:backend` reports 21 unrelated
files. Changed K3s files pass targeted Ruff checks.
