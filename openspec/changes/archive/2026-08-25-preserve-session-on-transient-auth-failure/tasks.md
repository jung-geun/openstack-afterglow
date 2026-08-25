## Implementation Tasks

- [x] Add deterministic regressions for concurrent session-record mutation and transient auth dependencies.
- [x] Replace whole-record session rewrites with Redis-atomic mutation that preserves token, activity, and blacklist fields.
- [x] Return retryable service errors without deleting valid refresh sessions when Redis or Keystone is temporarily unavailable.
- [x] Preserve browser auth state when refresh or `/auth/me` fails with a retryable error while retaining terminal 401 logout behavior.
- [x] Run exact backend/frontend authentication targets, then the project-wide test and lint gates.
- [x] Archive the completed change with `--skip-specs`.
