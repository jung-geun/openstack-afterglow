## Implementation Tasks

- [x] Update dev build-target selection so backend changes include frontend.
- [x] Verify workflow syntax and target-selection behavior.
- [x] Push to dev and confirm backend, worker, and frontend image jobs complete.

## Evidence

- 2026-08-02: Ruby parsed `.github/workflows/docker-build.yml` successfully. The GitHub Actions run for `2c3dae05` selected and completed all three amd64 image builds plus frontend, backend, and worker manifests: https://github.com/openstack-afterglow/openstack-afterglow/actions/runs/30755768903
