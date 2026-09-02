## Implementation Tasks

- [x] Correct Lumen API identity labels and remove legacy Afterglow configuration/encryption aliases.
- [x] Make Lumen Kolla lifecycle dispatch fail closed for unsupported actions and keep the local console development-only.
- [x] Bump, validate, release, and checksum the updated Lumen service, SDK, images, and `lumen-kolla` wheel.
- [x] Pin the released `lumen-kolla` wheel in Afterglow and remove the embedded Lumen role without fallback.
- [x] Remove unused AI runtime dependencies, obsolete chat worker resources, and Lumen runtime secret inputs from Afterglow.
- [x] Preserve and test Afterglow's authenticated chat BFF, streaming, frontend, and delegated MCP bridge.
- [x] Replace stale Afterglow-owned chat documentation with the Lumen integration contract.
- [x] Run focused Lumen/Afterglow contracts, full repository gates, and independent review.
- [ ] Perform a package-only live Kolla Lumen cutover without changing the existing Kolla-Ansible lock.
- [ ] Archive the completed change.
