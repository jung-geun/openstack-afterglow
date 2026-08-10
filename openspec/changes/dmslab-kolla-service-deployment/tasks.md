# Tasks

- [x] Verify existing Drover and Waygate repository promotion against the monorepo service trees.
- [x] Create isolated `drover`, `waygate`, and `palimpsest` developer workspaces.
- [x] Add independent Drover CI/CD and publish Drover API/worker `dev` images from its repository.
- [x] Add independent Waygate CI/CD and publish Waygate API/worker `dev` images from its repository.
- [x] Restrict the Afterglow image workflow to Afterglow API, frontend, and worker images.
- [ ] Extract the Palimpsest Hub API/worker and a versioned client into the Palimpsest repository.
- [ ] Migrate Afterglow callers to immutable Drover, Waygate, and Palimpsest SDK/client revisions.
- [ ] Remove duplicate service source/image stages from Afterglow after all consumers cut over.
- [ ] Configure Kolla roles with immutable standalone service images without altering unrelated roles.
- [ ] Deploy only Afterglow, Palimpsest, Drover, and Waygate roles.
- [ ] Verify containers, Keystone identities, internal health, and public endpoint routing.
