# Database connection pool configuration

## Goal
Ensure every Afterglow SQLAlchemy worker uses the configured async database connection pool and timeout settings instead of silently falling back to defaults.

## Scope
- Apply the configured pool size, overflow, connection timeout, pool wait timeout, and unhealthy circuit duration to the API, chat worker, Notion worker, and Drover worker.
- Add regression coverage for pool engine options and worker settings compatibility.

## Non-goals
- Change default pool sizes or database URL formats.
- Replace SQLAlchemy sessions or add a new database backend.
