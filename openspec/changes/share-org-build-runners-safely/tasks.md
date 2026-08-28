## Repository hardening

- [x] Skip the self-hosted build matrix for pull-request events while preserving hosted tests and trusted push, tag, and dispatch builds.
- [x] Add an orchestration contract proving pull requests cannot schedule self-hosted builds.
- [x] Run the exact orchestration test, `npm run test:orchestration`, and `npm run test:gate`.
- [ ] Commit and push the hardened workflow to `dev`.

## Organization pool

- [ ] Enable public repositories on the organization Default runner group.
- [ ] Restore organization registration for five Linux x64 runners and recreate only the Afterglow runner service.
- [ ] Verify the runner group is visible to the repository and all five runners are online with expected labels.
- [ ] Verify a trusted workflow assigns and completes work on the organization pool.

## Completion

- [ ] Archive this change after all local and remote verification succeeds.
