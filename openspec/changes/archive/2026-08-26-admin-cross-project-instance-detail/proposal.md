## Why

The administrator all-instances page lists servers across projects, but its shared detail panel sends the selected server's project as `X-Project-Id`. Keystone attempts to rescope the human administrator into that tenant project and returns Unauthorized when the administrator has system-wide authority but no explicit tenant role. The frontend interprets those authorization 401 responses as expired access tokens, repeatedly refreshes a valid session, and never loads the detail.

## What Changes

- For a foreign `X-Project-Id`, validate the JWT session's current/home project first.
- If that live Keystone result proves `is_system_admin`, reuse the valid admin-scoped Keystone token while treating the explicit header project as the logical resource/audit/cache scope.
- Keep non-admin foreign-project access fail-closed with 403, and keep a genuinely invalid home session at 401.
- Construct OpenStack connections with the token's real scope while retaining the target project marker used by ownership checks and cache keys.
- Add deterministic authorization and connection-scope regressions plus a live administrator foreign-project instance-detail check.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- System administrators can inspect and operate on existing resources in an explicitly selected foreign project without receiving a tenant role assignment.

## Impact

The change is confined to JWT project-scope resolution and OpenStack connection metadata. Existing frontend admin detail composition already supplies the selected instance project. Tenant users cannot gain cross-project access, refresh/session security remains unchanged, and resource creation in foreign projects is not broadened by this change.
