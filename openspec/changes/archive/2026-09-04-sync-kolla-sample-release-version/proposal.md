## Why

Afterglow 1.18.1 release metadata is synchronized across packages and Helm, but `deploy/kolla/globals.afterglow.sample.yml` still pins `afterglow_image_tag` to `v1.18.0`. Operators copying the release sample would deploy the previous image, and the existing release scripts cannot detect or repair that drift.

## What Changes

- Make `scripts/sync-version.js` update the Kolla sample's `afterglow_image_tag` from the root package version.
- Make both version check implementations reject a Kolla sample tag that differs from the package version.
- Replace the Kolla contract's hard-coded historical tag assertion with a package-version-derived assertion.
- Synchronize the 1.18.1 Kolla sample before tagging the release.

## Capabilities

### New Capabilities
- Release version synchronization includes the operator-facing Kolla image tag sample.

### Modified Capabilities
- Version checks fail when package, backend, frontend, Helm, or Kolla sample versions drift.

## Impact

`scripts/sync-version.js`, `scripts/check-version-sync.js`, `scripts/check-version-sync.sh`, `scripts/kolla-contract.test.js`, and `deploy/kolla/globals.afterglow.sample.yml`. Runtime service behavior and live operator overrides are unchanged.
