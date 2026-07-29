## Why

After the active chat-platform adoption is complete, Afterglow needs a safe way to execute generated code and user-selected assistant code blocks. ClickHouse `code-interpreter` provides a sandboxed HTTP execution service, but it must be integrated through Afterglow's authenticated, durable run model rather than exposed directly to browsers or the model provider.

## What Changes

- Add an operator-configured pool of ClickHouse Code Interpreter API endpoints, authenticated only by server-side credentials and admitted only when the sandbox runtime is healthy and hardened.
- Add a project-scoped execution broker that selects a healthy interpreter by capacity, tracks in-flight work, applies bounded retry only before execution acceptance, and records an immutable execution identity/result in the chat run journal.
- Add a policy-aware `code_interpreter.execute` tool for approved code-mode agent runs. It may execute generated code automatically only through the durable tool/approval policy; ordinary chat messages never execute code implicitly.
- Add a separate Run button for renderable assistant code blocks. The button creates an owned, durable execution request and displays bounded stdout, stderr, exit status, and owned artifacts. It does not send browser credentials or call sandbox endpoints from the client.
- Support only the Code Interpreter service's configured runtimes and bounded source/stdin/files. Enforce language allowlists, execution limits, artifact scanning/ownership, output redaction, and no-network sandbox policy.
- Add runtime capability discovery, admin health/capacity diagnostics, audit events, backpressure, cancellation, and fail-closed behavior when no eligible interpreter is available.

## Capabilities

### New Capabilities

- **Durable sandbox execution**: execute a bounded code payload through an authenticated ClickHouse Code Interpreter pool and persist/replay safe execution state.
- **Assistant code-block execution**: let an authorized user explicitly run a supported assistant code block and inspect its bounded result and artifacts.
- **Interpreter pool scheduling**: select healthy configured interpreters by available capacity with circuit breaking and no duplicate execution after uncertain delivery.

### Modified Capabilities

- **Chat runtime capabilities**: advertise code-interpreter availability only when both the selected model/run policy and a healthy hardened interpreter pool permit it.
- **Chat tool policy and journal**: classify sandbox execution as a bounded process effect, apply approval/budget rules, and store only redacted result metadata outside encrypted run payloads.
- **Chat presentation**: render execution controls, queued/running/completed/failed/canceled state, output, and artifacts without treating output as trusted HTML.

## Impact

- Backend: chat contracts, migrations/ORM, runtime capability service, durable run executor, tool runtime, asset pipeline, configuration/generator/deployment manifests, and admin diagnostics.
- Frontend: chat code-block renderer, tool activity/result components, run reducer/stream contracts, and capability-aware controls.
- Infrastructure: ClickHouse Code Interpreter API/worker/file-storage deployment, Redis/S3 integration, isolated sandbox networking, service credentials, resource limits, and health/capacity telemetry.
- Security: arbitrary code is never executed in the Afterglow process, browser, host Docker socket, or unisolated fallback. Production requires the Code Interpreter hardened deployment profile; NsJail-only local mode is development-only.
