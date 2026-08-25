## Why

Active dashboard sessions are being cleared during routine use. The session path currently conflates credential invalidity with transient Redis or Keystone failures, deletes refresh state after any Keystone validation exception, and performs concurrent whole-record Redis rewrites that can restore an obsolete Keystone token. The frontend then treats any `/auth/me` failure as proof that the local session is invalid and propagates the logout to every tab.

## What Changes

- Make refresh-session field updates atomic so `last_seen`, refreshed Keystone tokens, and blacklist state cannot overwrite each other.
- Preserve refresh state when Keystone or Redis is temporarily unavailable; return a retryable service error while continuing to reject the protected request.
- Delete refresh state only for confirmed invalid credentials or explicit revocation/timeout.
- Make browser refresh and `/auth/me` verification distinguish terminal authentication failures from retryable transport/service failures.
- Add deterministic regressions for the Redis update race, transient backend failures, and browser-side session preservation.

## Capabilities

### New Capabilities

- Authenticated sessions survive temporary control-plane and session-store outages without weakening fail-closed authorization.
- Concurrent session metadata updates preserve every security-relevant field.

### Modified Capabilities

- Authentication failures remain HTTP 401 and clear local session state only after refresh cannot recover.
- Availability failures return HTTP 503, reject the current request, and retain refresh/local session state for retry.

## Impact

- Backend authentication dependencies, refresh rotation, and Redis session mutation semantics change.
- Frontend API refresh and root authentication bootstrap stop converting retryable failures into logout.
- No token TTL, binding mode, authorization rule, or explicit logout behavior is weakened.
