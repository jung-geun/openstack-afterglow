# Service repository promotion

Waygate, Drover, Lumen, and their OpenStack SDKs are self-contained distributions under `services/`. Promotion to standalone repositories is a history-preserving directory split; it does not require moving or rewriting service source code.

## Preconditions

Before splitting a distribution:

1. Complete and archive the active OpenSpec change.
2. Run the monorepo test and lint gates from the repository root.
3. Confirm that the service distribution contains no `app.*` imports and that Afterglow imports the service only through its `<service>_sdk` package.
4. Choose the target repository and its protected default branch.

## Split a distribution

Run the split from the Afterglow repository root. Replace `<distribution>` with one of `waygate`, `waygate-sdk`, `drover`, `drover-sdk`, `lumen`, or `lumen-sdk`.

```bash
git subtree split --prefix="services/<distribution>" -b "<distribution>-split"
git init --bare "../<distribution>.git"
git push "../<distribution>.git" "<distribution>-split:main"
```

For a hosted repository, replace the local bare-repository URL with the hosted Git URL. The split branch contains only the selected directory while preserving commits that affected it.

## Reconnect Afterglow

After the standalone package is published:

1. Replace the corresponding path dependency in `backend/pyproject.toml` with the released SDK version. Afterglow depends on `waygate-sdk`, `drover-sdk`, and `lumen-sdk`; it does not depend on service implementation packages.
2. Refresh `backend/uv.lock` through the normal dependency workflow.
3. Point the Kolla role at the new image build pipeline:
   - Waygate: `waygate_api_image`, `waygate_worker_image`, `waygate_image_tag`
   - Drover: `drover_api_image`, `drover_worker_image`, `drover_image_tag`
   - Lumen: `lumen_api_image`, `lumen_worker_image`, `lumen_image_tag`
4. Run the catalog SDK round-trip, proxy, explicit-unavailability, migration-idempotency, health, and full monorepo gates before deployment.

No service source changes are part of promotion. If a split service imports `app.*`, or Afterglow imports service implementation modules instead of `<service>_sdk`, fix that boundary in the monorepo before splitting rather than carrying a compatibility shim into the new repository.
