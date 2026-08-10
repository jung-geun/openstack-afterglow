# Standalone service repositories and DMSlab deployment

## Goal
Move Drover, Waygate, and Palimpsest service delivery out of the Afterglow monorepo. Each service must be developed in its own repository and workspace, test and publish its own OCI images, and be deployed into DMSlab by explicit image reference without changing unrelated OpenStack services.

## Scope
- Treat `openstack-afterglow/drover` and `openstack-afterglow/waygate` as the source of truth: verify their promotion parity, give each an independent `dev` CI/CD pipeline, and publish API/worker images from that repository only.
- Stop the Afterglow GitHub workflow from selecting, building, or publishing Drover and Waygate images. Afterglow continues to publish only its API, frontend, and worker.
- Extract the server-side Palimpsest Hub API/worker into `openstack-afterglow/palimpsest`, where the existing local CLI already lives, with a versioned client boundary for Afterglow.
- Replace Afterglow implementation dependencies with immutable SDK/client revisions. Remove duplicate service source and image stages only after every caller has cut over.
- Configure Kolla roles with explicit standalone image references and deploy only the custom roles once the images and service contracts are verified.

## Constraints
- Work only from `dev`; publish only committed, verified source.
- Preserve the existing Kolla inventory, services, passwords, and databases. No `destroy`, global `reconfigure`, or unscoped Kolla deployment.
- Do not expose or commit secrets.
- Public Drover/Waygate endpoints must keep the existing `drover.dmslab.re.kr` and `waygate.dmslab.re.kr` catalog contract.
- Palimpsest authorization, immutable blob digest storage, and project isolation must be preserved across the service boundary; no direct database-model import from Afterglow may remain.

## Risks
- A GitHub token can publish a package owned by its service repository but cannot publish it from the Afterglow repository; the root workflow already proved this restriction.
- The existing Palimpsest repository is a local KVM CLI, while the Hub API/worker currently share Afterglow models, database, and OpenStack services. Its extraction requires an explicit authenticated client and migration plan, not an image rename.
- The existing DMSlab catalog endpoints do not prove public DNS/proxy reachability; deployment remains blocked until standalone images and endpoint routing both work.
