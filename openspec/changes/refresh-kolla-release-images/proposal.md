## Why

The `v1.17.1` Docker images were published and the live Kolla globals reference the mutable Afterglow image names, but `kolla-ansible reconfigure --tags afterglow` never invokes the role's force-pull task. Existing local `latest` images are therefore reused even when GHCR already contains a newer release image.

## What Changes

- Force-pull enabled Afterglow backend, frontend, and worker images before remote-image deploy and reconfigure lifecycles use them.
- Validate the effective configured service image references rather than an unrelated base-name/tag expression.
- Document immutable release pinning and the required pull/upgrade handoff for production deployments.
- Add Kolla contracts for pull ordering and effective image-reference checks.
- Suppress loop values for every plugin image pull so service environment secrets never appear in Ansible output.

## Capabilities

### New Capabilities

- `kolla-ansible deploy` and `reconfigure` deterministically refresh configured Afterglow images before bootstrap, policy seeding, or container startup.

### Modified Capabilities

- Production operators can pin released linux/amd64 digests while mutable-tag development deployments still receive explicit remote refreshes.

## Impact

The Afterglow Kolla role gains a registry dependency during remote-image deploy and reconfigure. Source-build mode remains unchanged because the pull task already skips it. Existing digest-pinned deployments remain immutable until operators update their configured refs.
