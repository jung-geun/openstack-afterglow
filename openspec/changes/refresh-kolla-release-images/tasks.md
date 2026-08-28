## Implementation Tasks

- [x] Include force-pull before remote-image deploy bootstrap and reconfigure startup.
- [x] Validate every enabled Afterglow service's effective configured image reference.
- [x] Add Kolla regression contracts for pull ordering and effective-ref validation.
- [x] Document mutable-tag refresh and immutable release-digest handoff.
- [x] Suppress service-loop values during plugin image pulls so credential-bearing environments never reach Ansible output.
- [x] Run focused Kolla contracts, full repository tests, and backend lint.
- [ ] Update live Afterglow refs to the v1.17.1 linux/amd64 digests and run Kolla pull/upgrade twice.
