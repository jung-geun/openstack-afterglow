## Why

The prior consolidation work established service-owned SDK sources, but it described retirement of the standalone `drover-sdk`, `waygate-sdk`, and `lumen-sdk` repositories as deferred. The intended end state is stronger: those repositories must have no required consumers and must be removable without affecting Afterglow, the service image pipelines, or the service SDK distributions.

Current repository evidence establishes the source cutover: Afterglow resolves each package from the corresponding service repository's immutable `#subdirectory=sdk` revision, and each service repository carries and validates its own SDK. The remaining work is to make that deletion contract explicit, continuously check it, and record the operational removal boundary.

## What Changes

- Add a regression test that verifies both Afterglow dependency groups and the resolved lockfile source `drover-sdk`, `waygate-sdk`, and `lumen-sdk` exclusively from `openstack-afterglow/<service>.git#subdirectory=sdk` at immutable revisions.
- Update service-promotion documentation with the standalone-SDK retirement procedure: validate the consumer contract and service CI, remove the three legacy repositories only after the checks pass, and preserve no compatibility alias or PyPI publication.
- State the bounded deletion guarantee: it covers repositories and workflows owned by `openstack-afterglow`; unauditable third-party clones that directly pin a legacy Git repository must migrate independently before deletion.

## Capabilities

### New Capabilities

- `standalone-sdk-repository-removal`: Afterglow has a tested dependency-source contract and an operational checklist that makes the obsolete `drover-sdk`, `waygate-sdk`, and `lumen-sdk` repositories removable.

## Impact

`backend/tests/` gains packaging-configuration coverage and `docs/service-repository-promotion.md` gains the removal runbook. Runtime APIs, SDK package/import names, and service image behavior do not change. The legacy repository deletion itself is an administrative GitHub action, intentionally outside this code change; no repository is deleted automatically.
