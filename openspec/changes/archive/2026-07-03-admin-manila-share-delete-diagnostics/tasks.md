# Tasks

- [x] Confirm implementation runs on `dev` branch.
- [x] Create OpenSpec proposal and task artifacts.
- [x] Add `FileStorageDeleteDiagnostic` and `FileStorageForceDeleteResult` models.
- [x] Add Manila delete diagnostic helper functions.
- [x] Add Manila force-delete helper using documented `force_delete` action.
- [x] Add admin-only delete diagnostics API endpoint.
- [x] Add admin-only force-delete API endpoint with cache invalidation and activity logging.
- [x] Add frontend diagnostic and force-delete result types.
- [x] Fetch delete diagnostics after loading problematic file-storage details.
- [x] Render delete diagnostics, evidence, recommendation, refresh, and gated force-delete action.
- [x] Trigger diagnostics when normal delete fails.
- [x] Add backend service and API regression tests.
- [x] Add Manila low-level force-delete tests.
- [x] Add frontend panel diagnostics and force-delete tests.
- [x] Confirm file-storage creation behavior remains unchanged.
- [x] Run targeted backend tests.
- [x] Run targeted frontend tests.
- [x] Run repository-required `npm run test:all`.
- [x] Run repository-required `npm run lint:backend`.
- [x] Run manual admin UI smoke test or document unavailability.
- [x] Archive OpenSpec change with `--skip-specs --yes`.

## Verification notes

- Manual diagnostic/force-delete UI smoke against a problematic live share was not run because the dev backend returned 5 Manila shares and none had status `error`, `deleting`, or `error_deleting`.
- Partial browser smoke was run on `http://localhost:3080/admin/file-storage` with a system-admin login: the admin file-storage list loaded, an `available` share detail opened, and the diagnostic/force-delete section was absent as expected for non-problematic status.
