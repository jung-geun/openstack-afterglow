## Implementation

- [x] Replace the stale topology `200 | 500` live expectation with `200 | 503` and document the transient Keystone contract.
- [x] Run `npm run test:live:network` successfully (14 passed) and retain failed GitHub run `33137860119` as the pre-fix reproduction.

## Verification

- [x] Run `npm run test:gate` successfully.
- [x] Push the fix to `dev`; Docker Build & Push run `33139071633` published backend, frontend, and worker dev manifests.
- [x] Archive this change after the remote workflow succeeds.
