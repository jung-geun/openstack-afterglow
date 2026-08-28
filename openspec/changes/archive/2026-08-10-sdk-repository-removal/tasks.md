## Implementation Tasks

- [x] Audit Afterglow dependency groups, lockfile sources, service-owned SDK trees, and organization code references for legacy standalone SDK URLs
- [x] Define the deletion-safe boundary: all first-party consumers use immutable service-repository `sdk/` subdirectory revisions; external consumers remain responsible for their own migration
- [x] Add regression coverage for service-owned SDK dependency sources
- [x] Add an explicit standalone-SDK repository retirement procedure to the promotion documentation
- [x] Run focused packaging tests and required repository gates
- [x] Archive the completed OpenSpec change
