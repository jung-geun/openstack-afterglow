## Implementation

- [x] Add a shared Docker-style image reference parser and `latest` normalizer.
- [x] Expose canonical image name, repository, and tag from Glance service/model responses.
- [x] Normalize public upload, snapshot, and public/admin rename requests before Glance mutations.
- [x] Update frontend image types, selectors, cards, details, and admin table/edit labels.
- [x] Add backend and frontend regression coverage for parsing and version selection.

## Verification

- [x] Run focused backend image tests and frontend image tests (66 backend tests; 7 frontend tests).
- [x] Run backend lint/format checks and focused frontend checks. Full frontend `svelte-check` retains existing unrelated baseline errors.
- [ ] Run the applicable full test gates.
