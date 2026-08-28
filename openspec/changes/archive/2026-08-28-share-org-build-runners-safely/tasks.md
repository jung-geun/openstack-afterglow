## Repository hardening

- [x] Skip the self-hosted build matrix for pull-request events while preserving hosted tests and trusted push, tag, and dispatch builds.
- [x] Add an orchestration contract proving pull requests cannot schedule self-hosted builds.
- [x] Run the exact orchestration test, `npm run test:orchestration`, and `npm run test:gate`.
- [x] Commit and push the hardened workflow to `dev` as `72f39f92`.

## Organization pool

- [x] Enable public repositories on the organization Default runner group.
- [x] Restore organization registration for five Linux x64 runners and recreate only the Afterglow runner service.
- [x] Verify the group is visible to this public repository and the clean organization pool has five x64 plus two ARM64 runners online.
- [x] Verify trusted build job `98764856659` runs on Default-group organization runner `linux-afterglow-runner-0dccfbf6a0be` and completes successfully.

## Completion

- [x] Archive this change after all local and remote verification succeeds.
