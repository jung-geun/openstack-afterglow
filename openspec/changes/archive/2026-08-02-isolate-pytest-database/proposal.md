# Isolate Pytest Database

## Why

The active development backend and `npm run test:db` both use `afterglow_test`. DB-marked tests call `Base.metadata.drop_all()` during teardown, which erases the running application's schema and restarts workers into missing-table failures.

## What Changes

- Give the local pytest runner its own `afterglow_pytest` database.
- Create the database and grant the local test user before DB tests run.
- Reject DB-marked tests targeting the configured application schema, with an explicit exception for CI's ephemeral service database.

## Non-goals

- Change the running development database.
- Change production database provisioning.
