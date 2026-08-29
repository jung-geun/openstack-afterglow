## Implementation Tasks

- [x] Advance Drover API and SDK package versions to `0.2.0` and verify their lock metadata.
- [x] Pin Afterglow API and worker dependencies to the immutable Drover `0.2.0` source commit.
- [x] Advance every synchronized Afterglow version source and lock metadata to `1.18.0`.
- [x] Add the `1.18.0` changelog entry and update current/next version policy values.
- [x] Run Drover and Afterglow release verification gates.
- [x] Treat no-count GPU PCI aliases as quantity one when filtering project flavors.
- [x] Commit and push both development branches and open dev-to-main release pull requests.
- [ ] After the required manual main merges, create annotated Drover `v0.2.0` and Afterglow `v1.18.0` tags from their main merge commits.
- [ ] Verify versioned and `latest` GHCR images plus the `1.18.0` Helm chart are publicly resolvable.
