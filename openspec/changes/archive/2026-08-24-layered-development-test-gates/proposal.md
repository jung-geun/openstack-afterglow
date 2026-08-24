## Why

Afterglow already keeps Drover, Waygate, and Lumen behind service-owned repositories, immutable SDK revisions, and HTTP/Keystone boundaries, but its development gate does not reflect those boundaries. The current `test:all` mixes deterministic local tests with credential-dependent live OpenStack scenarios, GitHub Actions omits the test-target/Kolla contract runner, the DB-backed suite runs only after `dev` pushes, and extracted-service proxy/SDK contracts are buried inside the general backend suite. A contributor therefore cannot tell whether a failure belongs to local code, a service contract, local persistence, or the shared cloud.

Adopt the useful part of the OpenStack development model without copying Zuul or provisioning a full DevStack cloud: fast isolated unit tests, explicit consumer contract tests at service boundaries, local functional tests with disposable data services and fake external OpenStack dependencies, and a separately invoked live OpenStack scenario layer.

## What Changes

- Define four authoritative test layers:
  - `unit`: no Docker, network, credentials, or live service dependencies.
  - `contract`: Afterglow BFF routes, service SDK adapters, immutable dependency sources, and ingress/service-boundary compatibility.
  - `functional`: the real application persistence path against local MariaDB/PostgreSQL test services while OpenStack and extracted services remain faked.
  - `live`: credential-dependent scenarios against a running OpenStack cloud; never part of the deterministic local commit gate.
- Cut root npm scripts over to `test:unit`, `test:contract`, `test:functional`, `test:live`, `test:all`, and `test:gate`. `test:all` becomes the deterministic three-layer suite; `test:gate` adds backend lint. Live slices use `live:*` target names.
- Add an explicit `contracts` named target so service-boundary compatibility can be run independently before real infrastructure.
- Update the target-runner regression suite to enforce the new layer names, commands, preconditions, and clean removal of misleading `integration:*` aliases.
- Split GitHub Actions into orchestration, backend unit, service contract, local functional, frontend, and optional live OpenStack jobs. Local functional tests run for pull requests and `dev`; live tests remain gated by verified credentials and endpoint reachability.
- Update contributor and testing documentation with the layer contract, command matrix, failure ownership, and exact commit/live verification rules.
- Run the local functional layer through a dedicated disposable Compose project (MariaDB, PostgreSQL, Redis) with automatic teardown. Functional mode explicitly disables the ordinary fakeredis fixture so the local Redis boundary is real.

## Capabilities

### New Capabilities

- `layered-development-gates`: Contributors can identify and run the cheapest sufficient test layer, while the deterministic commit gate is independent of DMSLab availability.
- `service-consumer-contract-gate`: Extracted-service BFF, SDK, catalog, ingress, and dependency-source contracts have a dedicated local/CI signal.
- `local-functional-gate`: Database-backed behavior is exercised against disposable local services on pull requests instead of only after merging to `dev`.

### Modified Capabilities

- `targeted-local-testing`: Named targets remain available, but infrastructure-dependent scenarios are exposed as `live:*`, and project-wide verification uses the layered commands.
- `continuous-integration`: The reusable GitHub Actions workflow runs every deterministic layer and reports optional live-cloud availability separately.

## Impact

The change affects root test scripts, the target catalog and its regression tests, GitHub Actions, pytest marker documentation, contributor rules, and testing docs. It does not change production APIs, service ownership, database schemas, runtime configuration, SDK pins, or deployment topology. It deliberately does not add DevStack, Tempest, Zuul, cross-repository speculative checkout, or a new container artifact; those would require coordinated work in the service repositories and dedicated Linux runner capacity.
