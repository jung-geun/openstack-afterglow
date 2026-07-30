## Implementation

- [x] Add a shared Docker-style image reference parser and `latest` normalizer.
- [x] Expose canonical image name, repository, and tag from Glance service/model responses.
- [x] Normalize public upload, snapshot, and public/admin rename requests before Glance mutations.
- [x] Update frontend image types, selectors, cards, details, and admin table/edit labels.
- [x] Add backend and frontend regression coverage for parsing and version selection.
- [x] Add a Docker Hub-style repository catalog with tag drill-down, repository/tag search, facets, result counts, sorting, and empty states.
- [x] Reuse the same repository/tag query semantics in the VM image selector.

## Verification

- [x] Run focused backend image tests and frontend image tests (66 backend tests; 13 frontend tests).
- [x] Run backend lint/format checks and focused frontend checks. Full frontend `svelte-check` retains existing unrelated baseline errors; this change adds no new type errors.
- [x] Run the applicable full test gates. Frontend suite passed (877 tests); backend unit suite passed (3,773 passed, 61 skipped); backend lint/format checks passed. The backend integration suite remains blocked locally by the missing `os_service_project_id`.
