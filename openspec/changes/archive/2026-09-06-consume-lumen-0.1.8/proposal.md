## Why

Lumen released `v0.1.8` containing the UUID admission hotfix. Afterglow's Kolla operator environment and contract tests must update their pinned role wheel to consume `lumen-kolla==0.1.8` while preserving existing Kolla-Ansible and Drover pins.

## What Changes

- Update `deploy/kolla/operator/pyproject.toml` to pin `lumen-kolla` to the released `0.1.8` wheel URL and SHA256 (`fdef6b8ed0a8bb7f48364ba20cc9bb90471b162287d4d33f9cc13105c340a78b`).
- Regenerate `deploy/kolla/operator/uv.lock` with project-local `uv lock` so only the Lumen wheel URL, version, and hash change.
- Update operator and deployment documentation in `deploy/kolla/README.md` and `deploy/kolla/operator/README.md` to reference `v0.1.8`.
- Update `scripts/kolla-contract.test.js` mock versions and contract assertions to expect `0.1.8`.
- Update the installer’s expected `lumen-kolla` package version to `0.1.8`.

## Capabilities

### New Capabilities

- Operator Kolla environment installs and verifies the `lumen-kolla==0.1.8` role wheel package.

### Modified Capabilities

- Kolla contract tests assert `lumen-kolla` 0.1.8 wheel metadata, hash, and version strings.

## Impact

`deploy/kolla/operator/pyproject.toml`, `deploy/kolla/operator/uv.lock`, `deploy/kolla/install.sh`, `deploy/kolla/README.md`, `deploy/kolla/operator/README.md`, and `scripts/kolla-contract.test.js`. Application runtime, Docker Compose, and live operator state are untouched.
