# Tasks

- [x] Add fail-closed lifecycle action dispatchers to all four roles.
- [x] Split deploy, start, and reconfigure lifecycle tasks with checksum reconciliation.
- [x] Remove HAProxy, common-role, dynamic-group, and handler coupling.
- [x] Add direct internal-VIP ports, correct API origins, cache URLs, and secret-safe rendering.
- [x] Add immutable source checkout and local-image build contracts for all services.
- [x] Add managed Lumen PostgreSQL and fail-closed Afterglow bootstrap coverage.
- [x] Make installer and uninstaller additive exact-symlink operations.
- [x] Document isolated source-mode custom-playbook operation and DMSLab inputs.
- [ ] Add and document plugin-owned Kolla HAProxy internal-VIP routes with controller-local upstream ports.
- [ ] Replace DMSLab source-build inputs with exact GHCR linux/amd64 image digests.
- [ ] Re-run repository Kolla syntax/task-list checks and full test/lint gates for the revised topology.
- [ ] Install, baseline, deploy, reconfigure, and prove the DMSLab plugin deployment, including HAProxy fragments and unchanged reconfigure behavior.