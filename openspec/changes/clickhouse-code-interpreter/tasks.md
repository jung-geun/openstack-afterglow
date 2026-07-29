## Implementation Tasks

### Prerequisite and design lock

- [ ] Do not begin implementation until `builtin-ai-chat` has shipped the durable v2 tool/approval path, encrypted frozen selections, capability stream contract, and replay-safe tool journal required by this change.
- [ ] Confirm the supported ClickHouse Code Interpreter API/runtime contract against the pinned deployment version; record endpoint auth, health, runtime discovery, execute acceptance semantics, cancellation, output/artifact retrieval, and failure taxonomy.
- [ ] Define the execution contract: immutable request ID/idempotency key, project/user/run ownership, supported language/runtime allowlists, source/stdin/file bounds, CPU/memory/time/PID/output limits, artifact type/size bounds, and redacted public result schema.
- [ ] Define the broker delivery state machine and retry boundary. Retry only failures proven to occur before sandbox acceptance; never replay an execution after an ambiguous or accepted request.
- [ ] Define production admission requirements: hardened Code Interpreter deployment, isolated egress/no-network policy, authenticated server-side API access, service identity, resource quotas, health/capacity telemetry, audit retention, and an explicit development-only local profile.

### Backend schema, configuration, and scheduler

- [ ] Add additive migrations and ORM models for interpreter endpoints, immutable execution requests/results, attempt/dispatch records, artifact ownership, capacity leases, and audit events; register migration ledger coverage and replay-safe indexes/constraints.
- [ ] Add typed configuration for endpoint pool membership, secret references, runtime/language policy, resource/output limits, circuit-breaker thresholds, and development-only local-mode guard; synchronize `backend/app/config.py`, `generate_k8s.py`, and `afterglow.conf.example` with secrets rendered only through `render_secret()`.
- [ ] Implement a server-side Code Interpreter client with strict URL allowlisting, timeouts, request-size limits, authenticated headers, health/runtime discovery, bounded response parsing, and safe error classification; do not expose endpoints or credentials to browsers/models.
- [ ] Implement a project-scoped pool broker that admits only healthy hardened endpoints, selects capacity deterministically, tracks in-flight leases, applies circuit breaking/backpressure, and returns fail-closed unavailable responses when no eligible endpoint exists.
- [ ] Implement cancellation and reconciliation so abandoned durable runs release leases, retain immutable accepted-execution identity, never cause duplicate dispatch, and converge orphaned attempts/results safely.

### Durable chat integration and policy

- [ ] Extend runtime capability discovery so `code_interpreter` is advertised only for an authorized project, approved model/run mode, permitted runtime policy, and healthy eligible pool.
- [ ] Add the `code_interpreter.execute` tool contract for v2 code-mode agent runs with frozen arguments, policy/budget/approval checks, bounded payload validation, durable journal transitions, and replay-safe idempotency.
- [ ] Ensure generated-code execution is possible only after the durable tool/approval policy permits it; ordinary chat messages and unapproved code blocks must never execute implicitly.
- [ ] Persist encrypted sensitive request content separately from redacted replay/audit metadata; redact stdout/stderr/errors and treat all sandbox output, filenames, and MIME metadata as untrusted input.
- [ ] Implement project/user authorization and artifact ownership checks for request creation, status, cancellation, and download; scan/validate artifacts and serve them with safe content disposition/type handling.
- [ ] Add v1-only API routes plus `_AUDIT_PREFIX_MAP` registrations for user execution requests/results and admin endpoint diagnostics; enforce authentication, ownership, admin authorization, rate/concurrency limits, and fail-closed dependency errors.

### Frontend and operational surfaces

- [ ] Extend the chat stream/reducer contracts for queued, running, completed, failed, canceled, and unavailable execution events, including reconnect/replay ordering and stale-run protection.
- [ ] Add a capability-aware Run button to supported assistant code blocks. It must create a durable owned request through Afterglow, disable when policy/capability forbids it, expose cancellation where permitted, and never execute code in the browser.
- [ ] Render bounded plain-text stdout/stderr/status and sanitized artifact metadata/download controls; never inject sandbox output as HTML and preserve safe behavior during background refresh/replay.
- [ ] Add admin diagnostics for endpoint health, discovered runtimes, capacity, circuit state, recent redacted failures, and configuration validity without exposing credentials, code, tokens, or private artifacts.
- [ ] Add deployment manifests and observability for the hardened interpreter stack: API/workers, Redis/S3 dependencies, network isolation/egress rules, service credentials, resource limits, readiness/liveness, metrics, alerts, and a clearly separated development-local profile.

### Verification and release gate

- [ ] Add backend unit coverage for client parsing, endpoint admission, scheduler selection/circuit breaking, no-duplicate delivery, policy/approval gates, request bounds, redaction, authorization, artifact safety, cancellation, and reconciliation.
- [ ] Add migration and integration coverage using an isolated interpreter fixture for acceptance ambiguity, backpressure, restart/replay, endpoint failure, cancellation, and concurrent request/lease behavior.
- [ ] Add frontend tests for capability gating, explicit Run behavior, stream/replay transitions, failure/cancel states, output escaping, and artifact ownership presentation.
- [ ] Perform security review of the deployment profile, egress isolation, SSRF defenses, credential handling, arbitrary-code containment, output/artifact handling, BOLA/IDOR boundaries, and production-vs-local-mode guard.
- [ ] Run focused backend/frontend/integration tests, then `npm run test:all` and `npm run lint:backend`; record deployment smoke evidence against a hardened non-production environment before archiving the change.
