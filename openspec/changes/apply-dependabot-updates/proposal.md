# Apply Dependabot updates

## Goal

Apply open Dependabot dependency PR contents to `dev` without merging `main`-targeted PR branches.

## Scope

- Apply backend/root Python dependency updates from PRs #33, #34, #36, #37, #38, #39.
- Apply frontend dependency updates from PRs #31 and #35.
- Keep existing `main`-targeted PR merge/close decisions with pie_root.

## Completion

Dependency target versions are present in manifests/lockfiles, required tests and backend lint pass, and the updates are committed on `dev`.

Skipped PR #31 because `npm --prefix frontend run check` still fails after reverting the Vite/plugin update, indicating a pre-existing frontend type-check failure outside this dependency task.
