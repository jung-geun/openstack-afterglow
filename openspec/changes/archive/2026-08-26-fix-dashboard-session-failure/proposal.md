## Why

A late 401 from an access token that has already been superseded can trigger an unnecessary second refresh rotation. Because refresh rotation invalidates the former refresh session, concurrent protected requests can cascade into terminal 401 responses, clear browser authentication, and redirect a successfully refreshed user to login. Separately, the administrator version endpoint still reads the removed `Settings.k3s_version` field and returns 500.

## What Changes

- When a protected request receives 401, compare the token used for that request with the current in-memory access token. Retry once with the newer token without refreshing when the failed token is stale.
- Add a deterministic delayed-401 fan-out regression proving one refresh serves both concurrent callers without clearing authentication or redirecting.
- Remove the obsolete global K3s configuration field from the administrator version API, frontend type and panel, and mock state.
- Add an authenticated administrator version endpoint regression for the current runtime response shape.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Frontend authenticated API retry behavior for superseded access tokens.
- Administrator runtime version response shape after Drover control-plane extraction.

## Impact

The frontend auth client and its tests change, while backend refresh-JTI rotation and session deletion remain unchanged. The administrator version wire response no longer includes `config.k3s_version`; all frontend consumers are migrated in the same cutover. Drover availability fallback behavior remains out of scope.
