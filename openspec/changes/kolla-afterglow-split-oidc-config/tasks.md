## Implementation Tasks

- [x] Default backend and frontend operator sources to their split subdirectories.
- [x] Remove the empty GitLab OIDC secret environment override from backend service definitions.
- [x] Update Kolla documentation and sample comments for the split layout.
- [x] Add contract tests for split source paths and TOML-owned OIDC secret precedence.
- [x] Run focused Kolla and configuration tests.
- [x] Run full tests and backend lint.
- [ ] Reconfigure live Afterglow and verify effective OIDC settings without exposing secrets.
- [ ] Archive the completed change.
