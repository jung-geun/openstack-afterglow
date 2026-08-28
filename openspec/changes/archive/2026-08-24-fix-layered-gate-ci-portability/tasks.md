## Implementation Tasks

- [x] Add separate `test:orchestration` and `test:kolla:contract` commands while retaining the combined local `test:target:js` gate.
- [x] Run orchestration in the version job and Kolla contracts after backend dependency sync in the contract job.
- [x] Add regression coverage for command placement and missing-root-lockfile independence.
- [x] Run focused orchestration/Kolla tests and the deterministic commit gate.
- [x] Archive the OpenSpec change, commit/push the follow-up, and confirm GitHub Actions succeeds.
