# Admin volume delete recovery

## Goal

Add admin-only Cinder volume delete diagnostics and automated safe recovery for volumes stuck in `error_deleting` or related delete-failure states.

## Scope

- Add typed backend response models for volume delete diagnostics, dependency evidence, recovery steps, and recovery results.
- Add Cinder/service helpers that classify stuck delete failures using volume status, attachments, snapshots, backups, Cinder messages, and final absence verification.
- Add admin-only API endpoints under `/api/v1/admin/volumes/{id}` for delete diagnostics and recover-delete execution.
- Extend the admin volume detail panel to fetch, render, refresh, and run the recovery workflow.
- Add an admin volume table action for diagnostic/recovery-capable statuses.
- Add backend and frontend regression tests for diagnostics, recovery sequencing, endpoint behavior, cache invalidation, and UI gating.
- Update volume API documentation for the new admin endpoints.

## Non-goals

- Do not change normal owner-scoped `/api/v1/volumes/{id}` delete semantics.
- Do not automatically detach in-use volumes, delete snapshots, delete backups, or move dependent resources.
- Do not add database tables, config keys, CLI dependencies, credential escalation, or direct Cinder DB deletion.
- Do not include unrelated active frontend design-system work in this recovery feature commit.

## Acceptance criteria

- Admin users can retrieve structured delete diagnostics for stuck Cinder volumes.
- Non-admin users receive 403 for diagnostics and recover-delete admin endpoints.
- Recovery returns structured `blocked`, `deleted`, `delete_submitted`, or `failed` results rather than hiding workflow outcomes behind generic HTTP errors.
- Recovery refuses to mutate attached volumes or volumes with dependent snapshots/backups.
- Recovery attempts reset-status, normal delete, force-delete fallback, and final absence verification in the documented order when safe.
- The admin detail panel shows diagnosis, evidence, recommended action, step results, refresh, and a confirmation-gated recovery button for problematic volume states.
- Targeted backend/frontend tests pass.
- Repository-required `npm run test:all` then `npm run lint:backend` pass before commit/push.
