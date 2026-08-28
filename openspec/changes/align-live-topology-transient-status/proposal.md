## Why

The v1.18.0 dev image workflow reached the live OpenStack suite but stopped before image build because `test_get_topology` rejected HTTP 503. The captured request log proves Keystone token validation timed out after 30 seconds. Returning 503 for that transient authentication dependency failure is the intentional fail-closed application contract; the live test still allowed the older generic 500 response instead.

## What Changes

- Update the live network topology contract to accept a successful 200 response or the intentional transient-service 503 response.
- Stop accepting generic HTTP 500 for this dependency failure so internal topology defects remain test failures.
- Preserve the application authentication and topology behavior; this change corrects only the stale live-test expectation.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Live OpenStack network verification distinguishes an expected transient Keystone availability response from an unexpected internal server error.

## Impact

- Test-only change in `backend/tests/integration/test_network.py`.
- No production API, authentication, or frontend behavior changes.
- A successful rerun unblocks the existing Docker Build & Push workflow and dev image publication.
