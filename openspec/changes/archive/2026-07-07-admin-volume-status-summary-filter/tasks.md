# Tasks

- [x] 1. Locate existing admin volume filters, list API, and aggregate candidates.
- [x] 2. Add an admin volume status aggregate source that returns true all-project counts.
- [x] 3. Add a reusable status summary UI that displays counts and drives the existing `statusFilter`.
- [x] 4. Wire the admin volumes page to load/refresh aggregate counts and reset pagination on status card selection.
- [x] 5. Add delegated backend/frontend regression tests.
- [x] 6. Run targeted verification and update this checklist.

## Verification

- [x] `cd backend && uv run pytest tests/test_admin_filters.py::test_volume_status_summary_counts_all_project_sdk_iterator -q`
- [x] `cd frontend && ./node_modules/.bin/vitest run src/lib/components/admin/volumes/__tests__/AdminVolumeStatusSummary.test.ts`
- `cd frontend && npm run check` was executed and still fails with existing repository-wide Svelte/type errors outside this change's modified files (63 errors, 223 warnings observed).
