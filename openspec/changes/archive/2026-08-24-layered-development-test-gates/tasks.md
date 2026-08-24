## Implementation Tasks

- [x] Define and document the `unit`, `contract`, `functional`, and `live` dependency contracts.
- [x] Cut root npm commands over to deterministic `test:all` and `test:gate` flows, with live OpenStack scenarios excluded from both.
- [x] Add the `contracts` named target for BFF, service SDK, ingress, and immutable dependency-source coverage.
- [x] Rename live named targets from `integration:*` to `live:*` without compatibility aliases.
- [x] Extend the test-target regression suite to enforce the layer catalog, exact selectors, required environment behavior, and removed aliases.
- [x] Move extracted-service boundary tests under an automatically marked `tests/contracts/` subtree so unit and contract layers do not execute the same tests.
- [x] Split GitHub Actions into orchestration, backend unit, service contract, local functional, frontend, and optional live OpenStack jobs.
- [x] Run local functional tests for pull requests and `dev` pushes using isolated MariaDB/PostgreSQL/Redis service containers.
- [x] Add a dedicated disposable functional Compose stack and make the DB runner use real Redis with fail-safe teardown.
- [x] Update `AGENTS.md`, `README.md`, and `docs/testing.md` with the layered development loop and commit/live verification rules.
- [x] Run exact orchestration tests, contract tests, the local functional layer, the deterministic full gate, and backend lint.
- [x] Obtain independent architecture/code review, resolve verified findings, then archive the OpenSpec change.
