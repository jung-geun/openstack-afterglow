## Why

Afterglow and the newly extracted Drover service have verified fixes on their development branches, but their public `latest` container tags still resolve to the older production revisions. A coordinated minor release is required so consumers can pull stable versioned images and the refreshed `latest` images without relying on mutable development tags.

## What Changes

- Release Drover API and SDK as `0.2.0`, preserving its existing dev-to-main publication contract.
- Pin Afterglow API and worker dependency groups to the immutable Drover `0.2.0` source commit.
- Release Afterglow as `1.18.0` across the root, frontend, backend, lock, and Helm chart version sources.
- Record the service API version-routing and GPU quota resilience changes in the Afterglow changelog.
- Use the existing main/tag workflows to publish versioned and `latest` GHCR images; do not create release tags from `dev`.
- Keep Kolla production references digest-pinned rather than changing them to mutable `latest` tags.

## Capabilities

### New Capabilities

- Consumers can pull the released Drover and Afterglow images through stable minor-version tags and refreshed `latest` tags after the required main merges and release tag.

### Modified Capabilities

- Afterglow's synchronized application and chart version advances from `1.17.1` to `1.18.0`.
- Drover's API and SDK package versions advance from `0.1.0` to `0.2.0`.

## Impact

The release changes package metadata, lockfiles, changelog/version documentation, and immutable Drover SDK pins. Runtime behavior remains the already-tested development-branch behavior. Production Kolla deployments remain unchanged until an operator explicitly replaces their image digests and runs the deployment workflow.
