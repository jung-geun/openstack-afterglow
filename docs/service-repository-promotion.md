# Service repository promotion

Waygate, Drover, and Lumen are self-contained service repositories under `services/`; each service tree includes its OpenStack SDK at `sdk/`. Promotion to standalone repositories is a history-preserving directory split; it does not require moving or rewriting service source code.

## Preconditions

Before splitting a distribution:

1. Complete and archive the active OpenSpec change.
2. Run the monorepo test and lint gates from the repository root.
3. Confirm that the service distribution and its `sdk/` distribution contain no `app.*` imports, the service root contains its own `LICENSE` and `Dockerfile`, and neither package has a dependency source path outside the service tree.
4. Confirm that service wheels resolve `afterglow-crypto` through its immutable direct Git dependency; do not restore sibling editable sources.
5. Choose the target repository and its protected default branch.

## Split a distribution

Run the split from the Afterglow repository root. Replace `<distribution>` with one of `afterglow-crypto`, `waygate`, `drover`, or `lumen`; each service split includes its `sdk/` directory.

```bash
git subtree split --prefix="services/<distribution>" -b "<distribution>-split"
git init --bare "../<distribution>.git"
git push "../<distribution>.git" "<distribution>-split:main"
```

For a hosted repository, replace the local bare-repository URL with the hosted Git URL. The split branch contains only the selected directory while preserving commits that affected it.

## Reconnect Afterglow

After the standalone service repository is published:

1. Point each `waygate-sdk`, `drover-sdk`, or `lumen-sdk` dependency in `backend/pyproject.toml` to the released service repository's `sdk` subdirectory at an immutable commit.
2. Refresh `backend/uv.lock` through the normal dependency workflow.
3. Point the Kolla role at the new image build pipeline:
   - Waygate: `waygate_api_image`, `waygate_worker_image`, `waygate_image_tag`
   - Drover: `drover_api_image`, `drover_worker_image`, `drover_image_tag`
   - Lumen: `lumen_api_image`, `lumen_worker_image`, `lumen_image_tag`
4. Run the catalog SDK round-trip, proxy, explicit-unavailability, migration-idempotency, health, and full monorepo gates before deployment.

Promotion must not change service behavior. Complete packaging prerequisites—license, standalone Dockerfile, and resolvable direct dependencies—before splitting. If a split service imports `app.*`, or Afterglow imports service implementation modules instead of `<service>_sdk`, fix that boundary in the monorepo before splitting rather than carrying a compatibility shim into the new repository.
