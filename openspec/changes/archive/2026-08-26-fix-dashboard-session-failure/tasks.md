## Implementation Tasks

### 1. Auth retry race

- [x] 1.1 Retry a protected request once with the newer in-memory access token when its failed token is superseded, without rotating refresh state again.
- [x] 1.2 Add a delayed concurrent 401 regression proving one refresh serves both callers and no auth clear or login redirect occurs.

### 2. Administrator version contract

- [x] 2.1 Remove obsolete `config.k3s_version` production from the administrator version endpoint.
- [x] 2.2 Remove the deleted version config field from the frontend type, panel, and mock state.
- [x] 2.3 Add an authenticated endpoint regression for the current response shape and absent `config` field.

### 3. Verification

- [x] 3.1 Run the focused frontend auth client test target.
- [x] 3.2 Run the focused backend administrator version endpoint test target.
- [x] 3.3 Run the named authentication regression target.
- [x] 3.4 Run the frontend unit regression target.
- [x] 3.5 Run the full repository validation gate.
- [x] 3.6 Verify the expired-token instance-detail flow and administrator version panel in a browser against the development stack.
