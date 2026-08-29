## Why

Extracted services are addressed through Keystone catalog endpoints and trusted internal overrides, but current clients either strip a hard-coded `/v1` unconditionally or append `/v1` unconditionally. Versioned endpoints can therefore become `/v1/v1/...`, while unversioned overrides can lose the required default version. Separately, optional Drover read-only enrichment must not block unrelated Afterglow flows, but quota, authorization, ownership, secret, and mutation decisions must remain fail-closed.

## What Changes

- Add version-aware service URL joining that preserves an endpoint's exact numeric API version segment (`v1`, `v2`, `v2.1`, and later numeric versions) and retains the request's default version only when the endpoint is unversioned.
- Apply the same URL contract to the Drover SDK, Afterglow HTTP/JSON service proxying, Drover shell WebSockets, and raw Zun requests.
- Keep direct extracted-service operations fail-closed while allowing explicitly optional, read-only dashboard and form enrichment to return an honest unavailable state without blocking unrelated data.
- Make GPU entitlement checks independent of the Afterglow database, classify GPU flavors from PCI passthrough aliases, run checks before resource allocation, and reject unavailable or malformed quota responses without leaking resources.
- Pin Afterglow to the corrected immutable Drover SDK commit and add regression coverage for URL composition, degraded reads, quota denial, service outage, and rollback safety.

## Capabilities

### New Capabilities

- **Catalog version inheritance**: Service clients append resource paths to the authoritative catalog/override version without duplicating or discarding version segments.
- **Explicit optional dependency degradation**: Read-only enrichment may degrade with availability metadata; required policy and feature calls never synthesize success.

### Modified Capabilities

- **GPU instance admission**: GPU quota checks are performed before mutation and fail closed for missing, unavailable, malformed, or denied quota responses.
- **Extracted service proxying**: Drover, Waygate, Lumen, Palimpsest, and applicable raw OpenStack service calls use the same version-aware URL contract.

## Impact

The change affects the Drover SDK repository plus Afterglow service proxy, WebSocket relay, Zun client, compute flavor/instance admission, dashboard quota/availability responses, focused backend contracts, dependency pins, and lockfile. Direct Drover APIs retain their existing error semantics. Optional dashboard data remains usable during Drover outages but is marked unavailable rather than represented as authoritative empty or unfiltered data.
