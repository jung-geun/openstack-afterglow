## Implementation Tasks

- [x] Backport catalog-relative `/v1` normalization and regression coverage in the Drover SDK repository.
  - Fixed in Drover commit `d332be7`.
- [x] Align Drover `FlavorInfo` with live Nova mapper fields and preserve GPU `extra_specs`.
  - Fixed in Drover commit `0e8bc44`.
- [x] Pin Afterglow backend dependencies to the immutable fixed Drover SDK commit and refresh `uv.lock`.
- [x] Run focused Drover SDK and Afterglow dependency/instance tests.
- [x] Keep Drover credential environments outside the HAProxy-visible Kolla service map.
- [x] Build and deploy the corrected Afterglow API and Drover service images through their normal image pipelines.
- [x] Verify the live GPU quota request uses `/v1/gpu-quotas/check` and the affected project receives the explicit unallocated-quota decision.
- [x] Run required repository gates and archive this change.
