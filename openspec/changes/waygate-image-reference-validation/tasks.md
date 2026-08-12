## Implementation Tasks

- [x] Add a fail-closed Waygate image-reference validator for remote digests and local source tags.
- [x] Validate every enabled API/worker runtime image reference before mutation.
- [x] Replace the legacy advisory API tag probe with exact-reference manifest inspection.
- [x] Add regression coverage for malformed digest length and exact configured references.
- [x] Run focused Waygate/Kolla tests, the complete suite, and backend lint.
- [ ] Correct the deployed worker digest, reconfigure Waygate, and verify both controllers.
- [ ] Archive the completed change.
