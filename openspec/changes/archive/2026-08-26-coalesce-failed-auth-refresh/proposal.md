## Why

The frontend coalesces refresh calls only while `/api/v1/auth/refresh` is pending. A fast refresh failure clears the shared promise immediately while the access token remains unchanged, so staggered 401 responses from an instance-detail fan-out each start another refresh. Once the backend's intentional `30/minute` limit is reached, rapid 429 responses make the gap self-amplifying and can produce hundreds of failed requests.

## What Changes

- Cache a settled refresh failure against the exact access-token and refresh-token generation.
- Reuse terminal refresh-401 outcomes until authentication state changes, and reuse retryable 429/503/network failures only for a bounded, status-aware cooldown.
- Check for a newer persisted cross-tab token before applying a cached failure.
- Add a deterministic staggered-401 regression proving one failed refresh serves the entire request cohort, preserves browser authentication on 429, and permits a new refresh after cooldown.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Frontend authenticated API refresh coalescing now covers recently settled failures, not only in-flight refresh requests.

## Impact

The change is confined to the frontend API client and its existing authentication regression suite. Backend refresh-JTI rotation, the `30/minute` rate limit, logout fencing, terminal redirect semantics, cross-tab winner adoption, and retryable-error session preservation remain unchanged.
