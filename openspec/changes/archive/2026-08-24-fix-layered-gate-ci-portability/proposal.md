## Why

The first pushed layered-gate workflow exposed a missing-runtime defect. `test:target:js` mixes pure Node orchestration tests with Kolla contract tests that spawn `uv`. The version/orchestration job runs before backend setup and installed `uv` only for tag pushes, so three Kolla tests failed with spawn `ENOENT` (`status: null`) and blocked every downstream layer. The Python patcher calls in those tests passed; deployment helper behavior is not implicated.

## What Changes

- Split pure test-runner orchestration from Kolla helper contracts into separate npm commands.
- Run pure orchestration in the version job and run Kolla contracts only in the service-contract job after `uv sync`.
- Add regression coverage for command placement so pure orchestration never requires `uv` and Kolla contracts run only after backend dependency setup.

## Capabilities

### New Capabilities

- `linux-ci-portable-layered-gate`: The layered workflow can run its orchestration and Kolla contracts in jobs that provide their actual runtime prerequisites.

### Modified Capabilities

- `layered-development-gates`: `test:target:js` remains the combined local gate, while CI consumes its pure orchestration and Kolla contract subcommands in separate jobs.

## Impact

The change affects only root test scripts, the reusable workflow, and their tests. Production Kolla helpers, deployment topology, and API behavior do not change.
