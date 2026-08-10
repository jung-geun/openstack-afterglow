# Kolla four-service deployment

## Goal
Deploy Afterglow, Drover, Lumen, and Waygate to the existing DMSLab Kolla-Ansible 2025.2 cloud through an isolated custom playbook, without changing stock Kolla playbooks, globals, passwords, HAProxy, inventory, or shared containers.

## Scope
- Make all four Kolla roles action-safe and lifecycle-scoped.
- Source-build all application images from immutable Git commits; retain reusable GHCR defaults.
- Add managed, controller-local Lumen PostgreSQL for the LangGraph checkpointer.
- Add an explicit, fail-closed Afterglow schema bootstrap and coverage.
- Install only role and aggregate-playbook symlinks into the selected Kolla installation.
- Document and validate the additive custom-playbook path.
- Deploy and prove the isolated plugin installation on `wireguard-dmslab` after local verification succeeds.

## Constraints
- Work only on `dev`; preserve unrelated working-tree contents, including root `test`.
- No changes to `/etc/kolla/globals.yml`, `/etc/kolla/passwords.yml`, stock `site.yml`, existing inventory, HAProxy fragments, shared containers, or non-plugin resources.
- All secrets are generated without logging and rendered only through protected plugin variables.
- Initial deployment and unchanged `reconfigure` must be repeatable and non-disruptive.

## Acceptance criteria
- Repository task lists for `deploy` and `reconfigure` contain only intended lifecycle tasks.
- `npm run test:all` then `npm run lint:backend` succeed.
- The DMSLab installation uses pinned source commits and direct internal-VIP listeners.
- Health, catalog/auth, provenance, no-touch, listener, and idempotent-reconfigure proofs are captured before archive.