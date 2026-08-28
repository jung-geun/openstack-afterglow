## Why

The administrator overview request can take longer than the frontend's 30-second request deadline when the optional Swift endpoint is degraded. The backend currently waits for the sequential all-project Swift fan-out and returns 200 only after the browser has already aborted, leaving the overview empty with a generic server error.

## What Changes

- Replace the Swift overview container listing with bounded account-metadata requests that disable connection retries.
- Count projects concurrently with explicit per-request and total deadlines; return the existing optional-service fallback value when the complete count cannot be collected in budget.
- Preserve the administrator overview response shape and the existing cache behavior.
- Add regressions for accurate cross-project totals, timeout fallback, concurrency, request timeout propagation, and connection cleanup.

## Capabilities

### New Capabilities

- Bounded Swift container aggregation for administrator overview data.

### Modified Capabilities

- Administrator overview remains responsive when Swift is unavailable or slow instead of completing after the frontend request deadline.

## Impact

The change is limited to the Swift service aggregation and backend tests. Healthy Swift deployments keep an accurate cross-project container count. Degraded or over-budget Swift collection reports `0`, matching the existing optional-service failure contract, while the rest of the overview remains available. No frontend wire contract changes.
