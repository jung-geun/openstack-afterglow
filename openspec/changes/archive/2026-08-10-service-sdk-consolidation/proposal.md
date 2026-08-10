## Why

`lumen-sdk`, `waygate-sdk`, and `drover-sdk` should be released and validated by the same repository that owns the corresponding service, not by separate standalone SDK repositories. Audit of the three standalone service checkouts (`waygate`, `drover`, `lumen`) confirmed each already nests its SDK distribution at `<service>/sdk`, keeps the public `<service>_sdk` package/import contract, and is the exact source Afterglow already depends on via an immutable `git+https://...#subdirectory=sdk` pin. Waygate and Drover already gate their image builds on a `sdk` CI job; Lumen's `docker-build.yml` built images without running its `sdk` job or the service test suite first, so nothing enforced SDK correctness before a Lumen image was published, and Afterglow's `lumen-sdk` pin trailed the owning repository's `dev` branch.

## What Changes

- Add a `sdk` CI job to Lumen's workflow (mirroring Waygate/Drover) and gate `docker-build.yml` on it, so Lumen tests and lints its SDK before publishing images — the same contract Waygate and Drover already enforce.
- Fix Lumen's `tests/test_cutover.py`, which asserted against `backend/migrations/075_drop_lumen_tables.sql` via a `../../../backend` path that only existed inside the former monorepo; the standalone repository cannot see Afterglow's tree, so the assertion is scoped to what the standalone repo can verify (its own baseline/cutover table set).
- Publish a new `dev` branch on `openstack-afterglow/lumen` (previously only `main` existed) so it follows the same branch convention Afterglow, Waygate, and Drover already use for owning-repository revision pins.
- Repin `lumen-sdk` in `backend/pyproject.toml` (main + worker groups) and `backend/uv.lock` from the stale `main` commit to the new `dev` HEAD commit that carries the SDK CI fix.
- Waygate and Drover already meet the target contract (nested `sdk/`, SDK CI job, image build gated on tests, Afterglow pinned to their `dev` HEAD) — no source or dependency changes needed for those two.

## Capabilities

### New Capabilities

- `service-owned-sdk-release`: Each of Waygate, Drover, and Lumen tests and lints its nested SDK in its own repository's CI, and gates its image publish on that CI, before Afterglow consumes a revision.

### Modified Capabilities

- `afterglow-service-sdk-dependencies`: Afterglow's `lumen-sdk` dependency source moves from a stale `main` commit to the current owning-repository `dev` HEAD, matching the existing `waygate-sdk`/`drover-sdk` pin convention.

## Impact

Lumen repository gains an `sdk` CI job and a `dev` branch; its `docker-build.yml` now depends on CI passing. Afterglow's `backend/pyproject.toml` and `backend/uv.lock` change only the `lumen-sdk` source commit; the package name, import path (`lumen_sdk`), and public contract are unchanged. No source-tree relocation occurs — the SDKs were already colocated with their services from a prior change; this change adds enforcement and refreshes one stale pin. `lumen-sdk`/`waygate-sdk`/`drover-sdk` are NOT published to PyPI (the `lumen-sdk` name is already squatted by an unrelated third-party PyPI project); the immutable Git `#subdirectory=sdk` dependency source remains the only distribution channel.
