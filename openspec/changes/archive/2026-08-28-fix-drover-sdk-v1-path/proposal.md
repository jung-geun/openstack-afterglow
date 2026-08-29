# Fix Drover SDK catalog-relative v1 paths

## Why

GPU instance creation calls `drover_sdk.Proxy.check_gpu_quota()` before creating the boot volume. Afterglow pins Drover SDK commit `274f39c6`, whose proxy sends `/v1/gpu-quotas/check` to an OpenStackSDK adapter that has already discovered the Drover `/v1` endpoint. The live request becomes `/v1/v1/gpu-quotas/check`, returns 404, and the SSE stream reports `Unrecognized schema in response body`.

## Evidence

- The browser receives the expected HTTP 200 `text/event-stream`; the failure is an application-level SSE event.
- Live Drover logs record `POST /v1/v1/gpu-quotas/check` with HTTP 404 at the failure timestamp.
- `POST /v1/gpu-quotas/check` exists and returns the expected authentication response.
- Current Drover `dev` normalizes `/v1` paths, but also changes the catalog service type to `container-infra`; pinning it directly fails against the currently deployed `drover` catalog entry.
- With the normalized SDK path, the live service reaches `/v1/gpu-quotas/check` but returns 400 because `nova.list_flavors()` supplies `ram`, `disk`, and `extra_specs` while `FlavorInfo` required `ram_mb` and `disk_gb` and discarded `extra_specs`.
- The live Kolla upgrade exposed Drover credential values because stock HAProxy tasks print each `drover_services` item and that shared map embedded runtime environments.

## What Changes

Backport catalog-relative path normalization and its regression test onto the service-owned Drover SDK commit currently consumed by Afterglow. Align Drover's `FlavorInfo` with every live caller so GPU extra specs survive quota usage calculation. Keep Drover credential environments outside the HAProxy-visible Kolla service map. Pin Afterglow to the resulting immutable Drover commit and refresh the lockfile. Do not bypass GPU quota checks, hardcode the live endpoint, weaken secret handling, or migrate the service catalog as part of this incident fix.

## Acceptance

- Drover SDK sends `/gpu-quotas/check` to the already versioned catalog adapter, never `/v1/v1/gpu-quotas/check`.
- Drover quota evaluation preserves the flavor's `ram`, `disk`, and GPU `extra_specs`.
- Kolla lifecycle output does not expose Drover credential environments.
- Afterglow uses the immutable service-repository SDK commit.
- Focused SDK and Afterglow dependency/instance tests pass.
- The live GPU quota check reaches the correct route and returns the configured quota policy. The affected project currently has no GPU quota, so it fails closed with an explicit unallocated-quota decision instead of a transport/schema error.
