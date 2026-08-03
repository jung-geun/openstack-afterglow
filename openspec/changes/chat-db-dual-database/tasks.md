## Implementation

- [x] Add PostgreSQL service and checkpointer DSN to the dev CI MariaDB job.
- [x] Start PostgreSQL alongside MariaDB in the local `npm run test:db` runner.
- [x] Start the real encrypted PostgreSQL checkpointer for v2 durable-run DB tests.
- [x] Preserve approval timestamp microseconds in the ORM schema and production migration.
- [x] Reproduce and resolve MariaDB approval HMAC failures without weakening validation.

## Verification

- [x] Run `npm run test:db` with MariaDB and PostgreSQL services.
- [x] Validate the test compose configuration and migration ledger checksum.
- [x] Run `npm run test:target:js` and `npm run lint:backend` on the clean commit tree.
- [ ] Run `npm run test:all` locally; the clean commit's JS and backend unit phases passed, but the integration phase requires unavailable OpenStack auth and failed before the frontend phase (`HTTP 422` admin login).
- [x] Push dev and confirm the Docker Build & Push workflow completes successfully (`14c5eb63`, run `30428749119`).
