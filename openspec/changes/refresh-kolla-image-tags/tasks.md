## Implementation Tasks

- [x] Add explicit remote-versus-source image pull policy to all five Kolla service roles.
- [x] Apply the pull policy to every long-running service container start task.
- [x] Replace stale Afterglow digest overrides in the operator sample with a release-tag contract.
- [x] Add Kolla contract coverage for mutable tags, immutable digests, and source-build isolation.
- [x] Run exact Kolla contract tests and repository validation gates.
- [ ] Migrate and verify the live Afterglow deployment on the v1.18.0 image tag.
- [ ] Archive the completed OpenSpec change.
