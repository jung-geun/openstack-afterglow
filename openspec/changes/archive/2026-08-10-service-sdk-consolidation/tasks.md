## Implementation Tasks

- [x] Audit standalone SDK parity, release workflows, and consumer dependencies for Waygate, Lumen, and Drover
- [x] Confirm Waygate already gates its SDK via service-owned CI (no change needed)
- [x] Confirm Drover already gates its SDK via service-owned CI (no change needed)
- [x] Add an SDK CI job to Lumen and gate its image build on service + SDK tests
- [x] Fix Lumen's cross-repo cutover test assertion that only worked inside the former monorepo
- [x] Publish Lumen's `dev` branch and verify its service/SDK CI lanes locally
- [x] Repin Afterglow's `lumen-sdk` dependency to Lumen's CI-fixed `dev` HEAD and refresh `backend/uv.lock`
- [x] Run focused backend verification and required repository gates
