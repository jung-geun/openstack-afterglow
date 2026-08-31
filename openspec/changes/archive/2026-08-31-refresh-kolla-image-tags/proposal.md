## Why

The Kolla plugin can keep running an older image even after an operator changes an image tag or expects `latest` to advance. Live Afterglow configuration currently pins explicit `afterglow_*_image_ref` digests from 1.17.1, which override `afterglow_image_tag`, and service container tasks rely on `community.docker.docker_container`'s cache-oriented default pull policy. The result is surprising: `pull`, `deploy`, or `reconfigure` may fetch exactly the configured immutable digest while never selecting the new release the operator intended.

## What Changes

- Define one remote-image contract for Afterglow, Drover, Lumen, Waygate, and Palimpsest: explicit tags are pulled from their configured tag, `latest` is checked against the registry every lifecycle run, and digest-pinned references remain immutable.
- Make service container tasks explicitly pull remote image references and avoid registry pulls for local source-build references.
- Preserve standalone `kolla-ansible pull` behavior and the existing deploy/reconfigure/upgrade ordering.
- Change the Afterglow deployment sample from explicit Afterglow digest overrides to `afterglow_image_tag`, while retaining immutable digest examples for independently released extracted services.
- Migrate the live Afterglow configuration from its stale 1.17.1 digest overrides to the published `v1.18.0` tag and verify the running image identity after Kolla reconfigure.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- Kolla image lifecycle operations now have explicit, consistent mutable-tag refresh behavior across every plugin service role.
- The Afterglow operator configuration can select a release tag without being silently overridden by stale per-image digest references.

## Impact

Every remote service container checks its configured image reference against the registry during deploy, reconfigure, and upgrade. When the registry resolves a mutable tag to a new image ID, `community.docker.docker_container` recreates the affected container; unchanged images remain idempotent. Source-build mode continues to use local SHA-tagged images without registry access. Digest-pinned service references continue to pull only the exact configured digest and never auto-upgrade.
