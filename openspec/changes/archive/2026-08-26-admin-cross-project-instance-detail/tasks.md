## Implementation Tasks

### 1. System-admin project scope

- [x] 1.1 Resolve foreign `X-Project-Id` requests by validating the JWT session's current project before attempting tenant rescope.
- [x] 1.2 Reuse the current scoped Keystone token only when the live result proves `is_system_admin`, while setting the logical target project for ownership, cache, and audit behavior.
- [x] 1.3 Keep the OpenStack connection authenticated to the token's real project scope and preserve the explicit target project marker separately.
- [x] 1.4 Return 403 for a valid non-admin session without target-project access and 401 for an invalid current session.

### 2. Regression coverage

- [x] 2.1 Add unit regressions for system-admin foreign-project fallback, non-admin denial, and invalid-current-session rejection.
- [x] 2.2 Add a connection regression proving the SDK connection uses the authenticated project while resource logic uses the target project.
- [x] 2.3 Add live coverage for an administrator opening a foreign-project instance when credentials are available.

### 3. Verification

- [x] 3.1 Run focused JWT/project-scope and admin instance tests.
- [x] 3.2 Run named auth and frontend regression targets.
- [x] 3.3 Run the full repository validation gate.
- [x] 3.4 Rebuild the backend and verify the administrator foreign-project detail cohort returns domain responses without refresh churn.
