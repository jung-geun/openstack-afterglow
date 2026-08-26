# Tasks

- [x] Confirm the live canonical Kolla globals contain mutable Waygate, Lumen, and Drover image names.
- [x] Resolve and verify the current published linux/amd64 manifests for all six service images.
- [x] Replace the six live service image names with immutable digest references.
- [x] Pin the bundled Lumen pgvector image to its approved immutable digest.
- [x] Run `kolla-ansible reconfigure -i multinode` to completion.
- [x] Verify API and worker containers on both controllers use the configured digests.
- [x] Verify internal and public Waygate, Lumen, and Drover health endpoints.
