## Implementation Tasks

- [x] Include force-pull before remote-image deploy bootstrap and reconfigure startup.
- [x] Validate every enabled Afterglow service's effective configured image reference.
- [x] Add Kolla regression contracts for pull ordering and effective-ref validation.
- [x] Document mutable-tag refresh and immutable release-digest handoff.
- [x] Suppress service-loop values during plugin image pulls so credential-bearing environments never reach Ansible output.
- [x] Run focused Kolla contracts, full repository tests, and backend lint.
- [x] Update live Afterglow refs to the v1.17.1 linux/amd64 digests and force-pull them on both controllers.
- [x] Restore SSH access, update the installed plugin, and reproduce two scoped upgrades against the v1.17.1 digest pins.
- [x] Reuse the complete start specification during upgrade so host networking and supplemental groups cannot drift.
- [x] Keep credential-bearing runtime environments outside `afterglow_services` and censor manifest assertion results.
- [ ] Deploy the follow-up fix, run two scoped upgrades, and verify both controllers' image digests and health.
