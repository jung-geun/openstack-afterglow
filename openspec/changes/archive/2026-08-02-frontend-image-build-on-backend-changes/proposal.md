## Why

A backend-only commit on `dev` currently produces backend and worker images but leaves the frontend image at its previous revision. The deployed frontend must be rebuilt alongside backend/worker changes so the release set advances together.

## What Changes

- Select the frontend image target whenever the dev-branch change detector selects backend and worker targets.
- Keep frontend-only changes frontend-only, and retain explicit workflow-dispatch target selection.
- Record the selection rule and verification result in the rapid OpenSpec checklist.

## Capabilities

### New Capabilities

- Dev backend changes publish a coordinated backend, worker, and frontend image set.

### Modified Capabilities

- Docker build target selection for dev pushes.

## Impact

- `.github/workflows/docker-build.yml` will run one additional frontend amd64 build and manifest when backend paths change on `dev`.
- No runtime application behavior, image contents, or release tag semantics change.
