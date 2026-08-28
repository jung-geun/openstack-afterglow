## Implementation

- [x] Replace the stale topology `200 | 500` live expectation with `200 | 503` and document the transient Keystone contract.
- [x] Run `npm run test:live:network` successfully (14 passed) and retain failed GitHub run `33137860119` as the pre-fix reproduction.

## Verification

- [x] Run `npm run test:gate` successfully.
- [ ] Push the fix to `dev` and verify Docker Build & Push publishes the dev image set.
- [ ] Archive this change after the remote workflow succeeds.
