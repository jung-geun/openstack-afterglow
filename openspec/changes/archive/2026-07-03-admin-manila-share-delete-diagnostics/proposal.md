# Admin Manila share delete diagnostics

## Goal

Add admin-only Manila share delete diagnostics and force-delete repair for stuck file-storage shares.

## Scope

- Add typed backend response models for delete diagnostics and force-delete results.
- Add Manila service helpers that classify stuck share delete failures using share metadata, share type extra specs, Manila messages, and share instances.
- Add admin-only API endpoints under `/api/v1/admin/file-storage/{id}` for diagnostics and force-delete repair.
- Extend the admin file-storage detail panel to fetch, render, refresh, and act on backend diagnostics.
- Add backend and frontend regression tests for diagnostics, force-delete, and UI gating.

## Non-goals

- Do not change normal owner-scoped `/api/v1/file-storage/{id}` delete semantics.
- Do not add database tables, config keys, CLI dependencies, credential escalation, or direct Manila DB deletion.
- Do not change file-storage creation behavior unless tests reveal the current implementation contradicts the approved plan.

## Acceptance criteria

- Admin users can retrieve delete diagnostics for stuck Manila file-storage shares.
- Non-admin users receive 403 for diagnostics and force-delete admin endpoints.
- Admin users can submit Manila `force_delete` for diagnostic-approved stuck shares and receive a 202 response.
- The admin detail panel shows diagnosis, evidence, recommended action, and a gated force-delete button for problematic share states.
- Targeted backend and frontend tests pass.
- Repository-required checks pass before the change is presented as commit-ready.
