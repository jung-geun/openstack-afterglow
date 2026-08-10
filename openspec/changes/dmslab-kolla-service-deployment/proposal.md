# DMSlab Kolla service deployment

## Goal
Publish deployable images for Afterglow, Palimpsest, Drover, and Waygate, then install and deploy their Kolla roles into the existing DMSlab OpenStack environment without changing unrelated OpenStack services.

## Scope
- Build and publish the seven required OCI images from the `dev` branch: Afterglow API, frontend, worker, Palimpsest worker, Drover API/worker, and Waygate API/worker.
- Make the Kolla installer work with the deployed Kolla-Ansible distribution and make the Afterglow role run the Palimpsest worker with persistent hub storage.
- Install the custom roles on the deployment host, use dedicated inventory groups and explicit image tags, then deploy only the custom roles.
- Verify containers, Kolla/Keystone identities, internal API health, and public routing when the DNS/proxy contract is available.

## Constraints
- Work only from `dev`; publish only committed, verified source.
- Preserve the existing Kolla inventory, services, passwords, and databases. No `destroy`, global `reconfigure`, or unscoped Kolla deployment.
- Do not expose or commit secrets.
- Public Drover/Waygate endpoints must match the existing `drover.dmslab.re.kr` and `waygate.dmslab.re.kr` catalog contract; do not replace them with incompatible port URLs.

## Risks
- The existing Kolla installation reports version `21.0.1.dev53`, while the installer currently rejects it.
- The current Kolla role omits the Palimpsest worker and its durable storage volume.
- The existing catalog contains Drover/Waygate endpoints but no corresponding service users or projects.
