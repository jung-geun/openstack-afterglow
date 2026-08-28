## Implementation Tasks

### 1. Refresh failure coalescing

- [x] 1.1 Cache settled refresh failures against the exact access-token and refresh-token generation.
- [x] 1.2 Apply a bounded retryable-error cooldown, honor longer valid `Retry-After` guidance for 429, and keep confirmed refresh 401 terminal until auth generation changes.
- [x] 1.3 Preserve cross-tab winner adoption, logout revocation fencing, and existing redirect/session-clear policy.

### 2. Regression coverage

- [x] 2.1 Add a staggered protected-401 regression where the first refresh returns 429 and every later caller reuses that failure without another refresh request.
- [x] 2.2 Prove retryable failure keeps browser auth, cooldown expiry permits one new refresh attempt, and adjacent refresh-401/503/network contracts remain green.

### 3. Verification

- [x] 3.1 Run the focused frontend auth client test target.
- [x] 3.2 Run the named authentication target and frontend unit target.
- [x] 3.3 Run the full repository validation gate.
- [x] 3.4 Rebuild the development frontend and verify an expired-token instance request cohort produces at most one refresh attempt, retains browser auth on retryable failure, and does not enter a 429 request storm.
