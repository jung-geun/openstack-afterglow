# Tasks

- [x] Confirm implementation runs on `dev` branch.
- [x] Create OpenSpec proposal and task artifacts.
- [x] Add typed volume delete diagnostic and recovery result models.
- [x] Add Cinder force-delete response status checking.
- [x] Add volume delete diagnostic helper functions.
- [x] Add recover-delete workflow with reset-status, normal delete, force-delete fallback, and absence verification.
- [x] Block recovery when the target volume is attached.
- [x] Block recovery when dependent snapshots or backups exist.
- [x] Add admin-only delete diagnostics API endpoint.
- [x] Add admin-only recover-delete API endpoint with cache invalidation and activity logging.
- [x] Add frontend diagnostic and recovery result types.
- [x] Fetch delete diagnostics after loading problematic admin volume details.
- [x] Render delete diagnostics, evidence, recommendations, step results, refresh, and gated recovery action.
- [x] Add admin volume table action for recoverable delete-failure statuses.
- [x] Add backend service and API regression tests.
- [x] Add frontend diagnostic section tests.
- [x] Update volume API documentation.
- [x] Run targeted backend tests.
- [x] Run targeted frontend tests.
- [x] Run repository-required `npm run test:all` in an isolated clean verification worktree.
- [x] Run repository-required `npm run lint:backend` after `npm run test:all`.
- [x] Commit and push the recovery feature to `dev`.
- [x] Archive OpenSpec change record.

## Verification notes

- `uv run --extra dev pytest tests/test_volume_delete_recovery.py tests/test_admin_volume_delete.py tests/test_mutation_invalidate_coverage.py -q` passed in `backend/`: 27 passed, 5 warnings in 0.30s.
- `npm test -- AdminVolumeDeleteDiagnosticSection` passed in `frontend/`: 1 test file passed, 4 tests passed.
- Clean isolated verification worktree `/tmp/afterglow-volume-recovery-verify` was prepared with only the committed recovery files on top of HEAD, excluding unrelated local design-system/admin UI worktree changes.
- `npm run test:all` passed in the clean verification worktree with `AFTERGLOW_ALLOW_INSECURE=1`, isolated Redis DB 15, and extended JWT/session TTLs: backend unit 2677 collected, integration 83 passed/129 skipped, frontend 40 files and 297 tests passed.
- `npm run lint:backend` passed in the source worktree after the clean `npm run test:all`: Ruff check clean, 417 files already formatted.
- Manual live admin UI recovery smoke against a real `error_deleting` volume was not run because no such target volume was provided during implementation; behavior is covered by mocked service/API tests and Svelte component tests.
- Unrelated active frontend design-system files remain uncommitted in the worktree; `openspec/changes/frontend-design-system-rules/tasks.md` still has its separate task 7/check verification unresolved and is out of scope for this recovery feature.
