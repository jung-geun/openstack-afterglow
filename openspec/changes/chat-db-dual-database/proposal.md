# Chat DB dual-database test lane

## Goal

Make MariaDB-backed chat integration tests exercise v2 durable-run behavior with a real PostgreSQL checkpointer, while preserving MariaDB timestamp precision required by approval HMAC validation.

## Scope

- Add a PostgreSQL test service beside MariaDB in CI and the local DB test profile.
- Start the real encrypted LangGraph PostgreSQL checkpointer for the v2 DB tests.
- Preserve microseconds in approval timestamps across MariaDB ORM schema creation and production migration.
- Keep v2 admission fail-closed when no PostgreSQL checkpointer is configured.

## Out of scope

- Replacing the production PostgreSQL checkpointer with an in-memory saver.
- Relaxing approval dispatch or decision HMAC validation.
