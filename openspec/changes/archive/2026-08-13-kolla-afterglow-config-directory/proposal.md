## Why

Afterglow's Kolla role stages operator input from `/etc/kolla/config/afterglow/afterglow.conf` but hard-overrides `afterglow_config_dir` to `/etc/kolla/afterglow`. Reconfigure therefore renders and mounts a different configuration tree than the operator-managed Kolla custom configuration directory, while `/etc/kolla/afterglow` also mixes runtime output with plugin globals and secrets.

## What Changes

- Make `/etc/kolla/config/afterglow` the default operator-input directory and write generated runtime files into its collision-safe `generated/` child.
- Remove the higher-precedence role var that forces `/etc/kolla/afterglow`.
- Default backend and frontend operator sources to `afterglow.conf` and `afterglow.frontend.conf` in the Kolla custom configuration directory.
- Discover optional sources by file existence, sanitize backend input, and project frontend input through the closed public allowlist before distribution.
- Mount only generated artifacts; Kolla-owned final values retain highest precedence and raw operator files never reach containers.
- Keep `/etc/kolla/afterglow` only for plugin `globals.yml` and `secrets.yml`.
- Add regression coverage for defaults, effective-variable precedence, source/output collision guards, generated destinations, projection, and container mounts.

## Impact

A scoped `kolla-ansible reconfigure --tags afterglow` migrates rendered Afterglow runtime configuration and mounts to Kolla's standard custom configuration tree. Existing plugin globals and secrets remain in `/etc/kolla/afterglow` and are not moved or deleted.
