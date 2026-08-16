# Tasks

- [x] Verify Drover, Lumen, and Waygate repository promotion against the monorepo service trees.
- [x] Create isolated `drover`, `lumen`, `waygate`, and `palimpsest` developer workspaces on `dev`.
- [x] Add independent service CI/CD and restrict the Afterglow image workflow to Afterglow-owned images.
- [x] Make Drover runtime OpenAPI and its SDK match the real Keystone, health, and cluster contracts.
- [x] Make Lumen runtime OpenAPI and its SDK distinguish Keystone, API-key, native-run, and BFF contracts.
- [x] Make Waygate runtime OpenAPI and its SDK match the real server, agent, and policy contracts.
- [x] Finish the Palimpsest Hub runtime OpenAPI, Keystone client, and safe resumable-upload contract.
- [x] Migrate Afterglow callers to immutable Drover, Lumen, Waygate, and Palimpsest SDK/client revisions.
- [x] Remove duplicate service source, tests, image stages, and embedded Palimpsest Hub ownership from Afterglow.
- [x] Configure Kolla roles with immutable standalone service images without altering unrelated roles.
- [ ] Deploy only the scoped Afterglow, Drover, Lumen, Waygate, and Palimpsest roles.
- [ ] Verify repository contracts, containers, Keystone identities, internal health, browser BFF behavior, and public endpoint routing.
