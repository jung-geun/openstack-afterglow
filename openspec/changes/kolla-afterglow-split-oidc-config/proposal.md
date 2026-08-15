## Why

Afterglow's Kolla role still discovers operator inputs at flat paths under `/etc/kolla/config/afterglow`, while the deployment now separates backend and frontend configuration into `backend/afterglow.conf` and `frontend/afterglow.conf`. A reconfigure therefore treats both sources as missing and replaces their generated layers with empty files. Independently, the backend container always injects `GITLAB_OIDC_CLIENT_SECRET`, defaulting it to an empty string; Afterglow's environment-first settings precedence then masks a valid client secret loaded from backend TOML.

## What Changes

- Default the backend operator source to `/etc/kolla/config/afterglow/backend/afterglow.conf`.
- Default the frontend public source to `/etc/kolla/config/afterglow/frontend/afterglow.conf`.
- Keep generated runtime artifacts isolated under `/etc/kolla/config/afterglow/generated`.
- Stop injecting an empty `GITLAB_OIDC_CLIENT_SECRET` environment variable into backend containers, and treat any stale empty value as absent when protected backend TOML provides a non-empty secret.
- Preserve Kolla-owned final settings and the frontend closed public projection.
- Add regression coverage for the split source layout and OIDC secret precedence.

## Impact

A scoped Afterglow reconfigure reads the new split files, recreates the backend when its generated configuration hash changes, and exposes the configured GitLab OIDC client secret to `Settings` without printing or duplicating it. Existing plugin globals and secrets stay in `/etc/kolla/afterglow`.
