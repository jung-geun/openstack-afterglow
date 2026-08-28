# Service Reconnection and CI Integration

## Why
Afterglow backend dependencies must be reconnected to released SDKs rather than local sibling path sources, and extracted service repositories (`waygate`, `drover`, `lumen`) require standalone GitHub Actions workflows to build and push container images to GHCR for Kolla deployment.

## What Changes
- Reconnect Afterglow `backend/pyproject.toml` to released git sources for `waygate-sdk`, `drover-sdk`, `lumen-sdk`, and `afterglow-crypto`.
- Add `.github/workflows/docker-build.yml` for `waygate`, `drover`, and `lumen`.
- Regenerate and publish split repository branches.
