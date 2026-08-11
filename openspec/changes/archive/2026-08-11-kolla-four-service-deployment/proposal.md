# Kolla four-service deployment

## Goal
Deploy Afterglow, Drover, Lumen, and Waygate to the existing DMSLab Kolla-Ansible 2025.2 cloud through an isolated custom playbook. Pull the four applications from immutable GHCR image digests and route their internal-VIP ports through Kolla HAProxy.

## Scope
- Make all four Kolla roles action-safe and lifecycle-scoped.
- Pull immutable GHCR image digests for the DMSLab deployment; retain optional source-build support for development.
- Add plugin-owned Kolla HAProxy service fragments for five HTTP frontends: Afterglow UI/API, Waygate, Drover, and Lumen.
- Bind application containers only to per-controller API-address upstream ports; HAProxy owns internal-VIP ports `3080`, `8020`, and `8010`–`8012`.
- Add managed, controller-local Lumen PostgreSQL for the LangGraph checkpointer.
- Add an explicit, fail-closed Afterglow schema bootstrap and coverage.
- Install only role and aggregate-playbook symlinks into the selected Kolla installation.
- Document and validate the additive custom-playbook path.
- Deploy and prove the isolated plugin installation on `wireguard-dmslab` after local verification succeeds.

## Constraints
- Work only on `dev`; preserve unrelated working-tree contents, including root `test`.
- Do not change `/etc/kolla/globals.yml`, `/etc/kolla/passwords.yml`, stock `site.yml`, existing inventory, or non-plugin resources.
- The custom playbook may use Kolla's `loadbalancer-config` and `loadbalancer` reconciliation path to add plugin route fragments. A fragment change may recreate the shared HAProxy container once; no unrelated service container may be restarted.
- Route only the internal VIP. Existing Drover and Waygate public FQDN catalog records remain external operator-owned DNS/TLS/ingress contracts.
- All secrets are generated without logging and rendered only through protected plugin variables.
- Initial deployment and unchanged `reconfigure` must be repeatable. Unchanged reconfigure must not restart HAProxy or plugin containers.

## Acceptance criteria
- Repository task lists for `deploy` and `reconfigure` contain only intended lifecycle tasks and the dedicated Kolla HAProxy route reconciliation.
- `npm run test:all` then `npm run lint:backend` succeed.
- DMSLab deploys exact GHCR image digests, and all five internal-VIP frontends are served by Kolla HAProxy.
- Health, catalog/auth, provenance, HAProxy-fragment, no-touch, listener, and idempotent-reconfigure proofs are captured before archive.