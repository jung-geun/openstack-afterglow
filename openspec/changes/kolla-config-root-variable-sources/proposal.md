## Why

Kolla-Ansible currently loads Afterglow plugin globals and secrets through `/etc/kolla/globals.d/90-openstack-afterglow-globals.yml` and `91-openstack-afterglow-secrets.yml`, whose live symlinks resolve to `/etc/kolla/afterglow/globals.yml` and `/etc/kolla/afterglow/secrets.yml`. This keeps an active deployment dependency outside Kolla's standard custom configuration tree even though Afterglow backend and frontend operator inputs already live under `/etc/kolla/config/afterglow`.

## What Changes

- Make `/etc/kolla/config/afterglow/globals.yml` and `/etc/kolla/config/afterglow/secrets.yml` the only plugin variable sources installed into Kolla's `globals.d` loader.
- Update install and uninstall ownership checks to use the standard configuration-root sources without retaining a legacy path alias or fallback.
- Update active deployment documentation and samples to describe the consolidated configuration tree.
- Add contract coverage that rejects active `/etc/kolla/afterglow` references and verifies both loader links use `/etc/kolla/config/afterglow`.
- Migrate the live deployment by moving the two protected source files with their existing ownership and modes, atomically repointing the two loader symlinks, and verifying an Afterglow reconfigure succeeds without reading the legacy directory. The directory itself is not deleted, but it no longer retains duplicate globals or secrets.

## Impact

Normal `kolla-ansible deploy` and `reconfigure` commands continue loading plugin variables from `globals.d`, but every active source is consolidated under `/etc/kolla/config/afterglow`. Backend and frontend operator inputs remain in their split subdirectories, generated runtime layers remain in `generated/` on service hosts, and protected values are not printed or duplicated into stock Kolla files.
