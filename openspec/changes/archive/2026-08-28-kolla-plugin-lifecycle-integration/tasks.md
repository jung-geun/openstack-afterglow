## Implementation Tasks

- [x] Add an aggregate-playbook preflight that fails enabled custom services lacking their inventory group, without changing stock Kolla playbooks.
- [x] Add Palimpsest to both plugin inventory samples and correct plugin lifecycle documentation for additive installer wiring and bare Kolla commands.
- [x] Make Afterglow upgrade include the shared source-mode-aware image pull task before policy seeding and restart.
- [x] Derive custom-service internal/admin URL and OpenStack interface defaults from standard Kolla protocol, FQDN, and interface globals while preserving explicit overrides.
- [x] Propagate standard Kolla OpenStack CA/insecure transport settings through Afterglow's generated runtime configuration with final Kolla ownership.
- [x] Replace Lumen's hardcoded Keystone domain/interface environment defaults with its existing Kolla-derived aliases.
- [x] Add contract and focused configuration regressions, then run exact targets for Kolla lifecycle and backend config behavior.
