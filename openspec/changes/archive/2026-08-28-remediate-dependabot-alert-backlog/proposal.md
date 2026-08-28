# Remediate Dependabot alert backlog

## Why

Remove every dependency vulnerability represented by the 119 open GitHub Dependabot alerts from `dev`, including Bun lock drift not covered by GitHub's npm lock scan.

## Current state

- 79 alert records are already fixed or removed in `dev` and remain open only because GitHub scans default branch `main`.
- 40 alert records remain vulnerable in `dev`: Pillow 12.1.1 accounts for 36 and Starlette 0.50.0 accounts for 4.
- `frontend/bun.lock` additionally retains esbuild 0.27.7 even though the npm lock no longer installs it.

## What Changes

- Upgrade Pillow to 12.3.0.
- Upgrade FastAPI to a release compatible with patched Starlette 1.3.1 and regenerate the backend lock.
- Enforce esbuild 0.28.1 or newer for frontend metadependencies and regenerate npm and Bun locks.
- Run focused dependency compatibility checks and the repository's mandatory test and lint gates.
- Do not dismiss accurate alerts; they must auto-close when `dev` reaches `main`.

## Completion

The `dev` manifests and locks contain no versions covered by the 73 unique advisories behind the 119 open alerts, focused compatibility checks pass, mandatory gates pass, and independent review confirms no manual dismissals are justified.
