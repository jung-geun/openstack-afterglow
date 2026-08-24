# Service repository promotion

Waygate, Drover, Lumen, and Palimpsest Hub are standalone service repositories. The duplicate in-tree service directories under `services/` and root Dockerfile build stages have been removed from Afterglow. Afterglow operates as a pure dashboard and BFF consumer, consuming extracted services via Keystone catalog discovery and immutable `#subdirectory=sdk` Git dependencies.

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

## Retire standalone SDK repositories

`drover-sdk`, `waygate-sdk`, and `lumen-sdk` are obsolete repositories. The
published SDK source is `<service>/sdk` in the corresponding service
repository; retain the package names (`drover-sdk`, `waygate-sdk`,
`lumen-sdk`) and Python imports (`drover_sdk`, `waygate_sdk`, `lumen_sdk`),
but do not retain a Git repository alias or publish a PyPI compatibility
package.

An organization administrator may delete each standalone SDK repository only
after all of the following pass:

1. Run `npm run test:target -- backend:tests/contracts/test_service_sdk_dependency_sources.py`.
   It verifies both Afterglow dependency groups and `backend/uv.lock` resolve
   every SDK from an immutable
   `https://github.com/openstack-afterglow/<service>.git#subdirectory=sdk`
   source.
2. Confirm the target revision remains reachable in the service repository and
   its service, SDK, and image-publish CI jobs are green.
3. Search every first-party repository and deployment manifest for
   `openstack-afterglow/drover-sdk`, `openstack-afterglow/waygate-sdk`, and
   `openstack-afterglow/lumen-sdk`; every result must be removed or migrated
   before deletion.
4. Delete the three legacy repositories. There is no redirect or compatibility
   alias after deletion.

This check covers repositories controlled by `openstack-afterglow`. An
independent third-party clone that pins a legacy Git URL must update its own
dependency before that URL is removed.

Promotion must not change service behavior. Complete packaging prerequisites—license, standalone Dockerfile, and resolvable direct dependencies—before splitting. If a split service imports `app.*`, or Afterglow imports service implementation modules instead of `<service>_sdk`, fix that boundary in the monorepo before splitting rather than carrying a compatibility shim into the new repository.
