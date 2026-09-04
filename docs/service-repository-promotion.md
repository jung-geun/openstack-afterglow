# Service repository promotion

Waygate, Drover, Lumen, and Palimpsest Hub are standalone service repositories. The duplicate in-tree service directories under `services/` and root Dockerfile build stages have been removed from Afterglow. Afterglow operates as a dashboard and BFF consumer: typed server-side integrations use immutable service-repository SDK dependencies, while the Lumen browser API uses the authenticated generic service proxy and does not install Lumen's AI runtime or SDK.

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

1. Point each SDK that Afterglow actually imports, currently `waygate-sdk` and `drover-sdk`, to the released service repository's `sdk` subdirectory at an immutable commit. Do not add `lumen-sdk` to Afterglow solely for BFF forwarding; direct Lumen clients consume it from the Lumen repository.
2. Refresh `backend/uv.lock` through the normal dependency workflow.
3. Point Kolla integration at immutable repository-owned role wheels and released image references.
4. Run typed SDK contracts where applicable, generic BFF proxy and streaming contracts for Lumen, explicit-unavailability, health, and full monorepo gates before deployment.

## Retire standalone SDK repositories

`drover-sdk`, `waygate-sdk`, and `lumen-sdk` are obsolete standalone repositories. Their published source lives under `<service>/sdk` in the corresponding service repository. Afterglow retains only the SDK packages it imports; the Lumen SDK remains available to direct Lumen clients but is intentionally absent from the Afterglow BFF runtime. Do not retain a legacy Git repository alias or publish a compatibility package.

An organization administrator may delete each standalone SDK repository only
after all of the following pass:

1. Run `npm run test:target -- backend:tests/contracts/test_service_sdk_dependency_sources.py`.
   It verifies Afterglow's required SDKs resolve from immutable service-repository
   `#subdirectory=sdk` sources and that unused `lumen-sdk` is absent.
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
