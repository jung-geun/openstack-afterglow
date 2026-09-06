## Implementation Tasks

- [x] Update `lumen-kolla` wheel URL and SHA256 in `deploy/kolla/operator/pyproject.toml` to v0.1.8
- [x] Regenerate `deploy/kolla/operator/uv.lock` using operator `uv lock` while preserving Kolla-Ansible and Drover pins
- [x] Update Lumen wheel version references in `deploy/kolla/README.md` and `deploy/kolla/operator/README.md`
- [x] Update Kolla contract test assertions and mocks in `scripts/kolla-contract.test.js` to 0.1.8
- [x] Update the Kolla installer’s expected `lumen-kolla` package version to 0.1.8
- [x] Parent verification and integration testing against live operator environment
- [x] Archive change after parent verification
