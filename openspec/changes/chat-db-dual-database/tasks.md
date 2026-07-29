## Implementation

- [x] Add PostgreSQL service and checkpointer DSN to the dev CI MariaDB job.
- [x] Start PostgreSQL alongside MariaDB in the local `npm run test:db` runner.
- [x] Start the real encrypted PostgreSQL checkpointer for v2 durable-run DB tests.
- [x] Preserve approval timestamp microseconds in the ORM schema and production migration.
- [x] Reproduce and resolve MariaDB approval HMAC failures without weakening validation.

## Verification

- [x] Run `npm run test:db` with MariaDB and PostgreSQL services.
- [x] Validate the test compose configuration.
- [ ] Run `npm run test:all` and `npm run lint:backend`.
- [ ] Push dev and confirm the Docker Build & Push workflow completes successfully.
