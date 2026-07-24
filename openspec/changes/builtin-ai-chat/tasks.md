## Implementation Tasks

`local://chat-capability-platform-plan.md` is the authoritative implementation contract. This ledger follows its rollout order. Completed historical tasks have focused-test evidence recorded below; no new platform task is complete until its stated focused verification passes.

### Verified historical built-in chat foundation

- [x] Resolve and lock existing LiteLLM/LangGraph baseline dependencies.
- [x] Synchronize initial chat configuration, encrypted provider models, MySQL conversation storage, credit ledger, and v1 audit mounts.
- [x] Deliver text streaming, conversation ownership, internal safe tools, stored pricing provenance, and focused backend/frontend tests.
- [x] Add chat model capability, citation, reasoning, tree, workspace, memory, agent, and extension baseline migrations through `036`.
- [x] Add the existing `037_chat_message_attachments.sql` attachment baseline.

### A0 — Canonical contracts and dependency gate

- [x] Add required direct capability-platform dependencies and verify the lock/import contract; keep MCP disabled if its exact supported streamable-HTTP contract cannot be proven.
- [x] Synchronize all exact `[chat]` retention, provider-route, memory, asset, scanner, and sandbox settings across config, generators, examples, and deployment secrets.
- [x] Define backend discriminated typed part, feature-option, event (including persisted execution-stage activity), descriptor, and usage-component contracts with strict size, recursion, and secrecy limits.
- [x] Move and extend frontend chat contracts with strict input/event parsing and safe display-only unknown-part placeholders.
- [ ] Migrate every legacy chat contract callsite to canonical parts/events without compatibility aliases outside the migration window.
- [x] Add focused contract, validation, wire, and dependency tests; run the `chat` target.

### A1 — Expand ledger and dual-read/write rollout

> Repository checkpoint: immutable manifest already records `039_chat_run_protocol.sql`,
> `040_chat_assets.sql`, `041_chat_jobs_memory.sql`, and
> `042_chat_message_parts_contract.sql`. The A1 tasks below remain unchecked until
> their migration runner, transactional boundaries, and focused verification are
> complete; the earlier plan filename placeholders are not used as completion evidence.

- [ ] Add immutable manifest-led migration runner and baseline ledger verification through the pre-run migration schema.
- [ ] Add the next available run-protocol migration with encrypted message parts, conversation lifecycle, runs, routes, events, approvals, jobs, usage reservations, temp threads, leases, turns, and segments.
- [ ] Add the next available asset migration with owned assets and message/run joins.
- [ ] Add the next available jobs-memory migration with derivations, memory provenance/outbox, and asset foreign keys.
- [ ] Add canonical-parts contract migration and defer legacy column deletion until the rollback window closes.
- [ ] Implement canonical encrypted message-part and transactional run-store boundaries, including project-and-user conversation ownership cutover.
- [ ] Implement A1 dual read/write plus forward and reverse backfill scripts with encrypted text-projection parity.
- [ ] Add migration dependency, ledger, ownership, encryption, dual-write, and rollback tests; run the `chat` target.

### A2/A3 — Backfill verification and canonical reads

- [ ] Verify production-compatible backfill completeness, decrypt/validate integrity, and text projection parity without replaying old migrations.
- [ ] Switch to canonical reads while preserving A1 dual writes for the rollback window.
- [ ] Add A1-to-A3 and A4a reverse-backfill rollback integration coverage.

### B — Durable run protocol and worker ownership

- [ ] Convert persistent, regenerate, and temp completion creation to idempotent `202` run descriptors with parent locking and versioned canonical fingerprints.
- [ ] Add owned run, active-run, temp-thread, approval, cancel, and SSE replay/reload routes with strict cursors and audit mappings.
- [ ] Implement MySQL-authoritative claim, lease, event sequencing, recovery, finalization, exact-once wallet reconciliation, and retention scheduler behavior.
- [ ] Add a separately deployed chat worker with Redis wakeup plus DB fallback, shared settings, lease recovery, and job backoff.
- [ ] Add run journal, idempotency, crash-boundary, cancel/approval race, atomic-finalization, deployment, and worker focused tests; run the `chat` target.

### C — Resumable graph and provider adapter

- [ ] Wire encrypted Postgres LangGraph checkpoints with explicit degraded behavior when unavailable.
- [ ] Replace the closure graph with resumable call-model, route-tools, execute/interrupt, and finalize nodes keyed by run UUID.
- [ ] Add canonical provider adapter plans, segments, message conversion, response normalization, replay of tool exchanges, and fixture coverage.
- [ ] Add provider route snapshots, pre-call config HMAC verification, segment crash markers, and explicit media routing without fallbacks.
- [ ] Add graph, checkpoint, provider-adapter, and crash-recovery focused tests; run the `chat` target.

### C — Capabilities, immutable pricing, and reservation gates

- [ ] Normalize LiteLLM/admin/model capability detection into canonical feature gates and exact provider media options.
- [ ] Resolve every requested route during run creation, freeze capability/pricing snapshots, and block active-route changes.
- [ ] Replace legacy usage cost with component-level immutable-pricing usage and exact Decimal reserve/reconcile accounting.
- [ ] Enforce provider parameter, context growth, output-combination, unavailable-route, and missing-price failures before provider calls.
- [ ] Add capability, lifecycle, pricing, reservation, and credit-race focused tests; run the `chat` target.

### D — Structured output and function/tool calling

- [ ] Add bounded structured-output schema validation, isolated validator process limits, canonical result persistence, and terminal error behavior.
- [ ] Add server-classified custom, built-in, MCP, code, and computer tool policies with bounded parallel execution and approval promotion.
- [ ] Persist approval interrupts and resume/deny/timeout handling without silent execution of mutations.
- [ ] Add structured output, tool policy, approval, batch-limit, and security focused tests; run the `chat` target.

### E — Native and managed search, fetch, and advisor

- [ ] Add exact native/managed search capability gates, route snapshots, pricing, and no-fallback behavior.
- [x] Extend the shared SSRF boundary with DNS-pinned safe fetch, redirect/domain policy, content extraction, and bounded untrusted tool results. Evidence: `backend/tests/test_chat_ssrf.py`, `backend/tests/test_chat_web_fetch.py`, `backend/tests/test_chat_tool_runtime.py` (2026-07-23).
- [ ] Add bounded advisor segments, hidden checkpoint-only advice, canonical activity/usage, and explicit failure warnings.
- [ ] Persist canonical citations and render them from the typed parts contract.
- [ ] Add search, fetch, advisor, citation, SSRF, and billing focused tests; run the `chat` target.

### F — Multimodal asset pipeline

- [ ] Add owned chat asset state-machine tables, secure upload/download/delete routes, asset audit mapping, joins, and cleanup serialization.
- [ ] Implement streaming validation, malware scanning, fixed-argv media inspection, encrypted object-store requirements, and fail-closed feature gates.
- [ ] Add input derivations and provider output ingestion with no client URL/base64 persistence.
- [ ] Extend composer, attachment strip, capability controls, mobile actions, and typed asset rendering using existing design primitives only.
- [ ] Add asset state, MIME/parser/scanner/S3, race, ownership, accessibility, and component focused tests; run the `chat` target.

### G — PostgreSQL pgvector semantic memory

- [ ] Expand encrypted MySQL memory scope, provenance, lifecycle, and migration invariants while preserving existing manual account memory.
- [ ] Implement content-free pgvector index, embedding route snapshots, ordered outbox leases, reindex generations/fence, and fail-closed retrieval.
- [ ] Add opt-in extraction, secret filtering, untrusted retrieval injection, retention/cleanup, and scope-aware CRUD/search APIs.
- [ ] Add memory settings UI with scoped controls and provenance without exposing embeddings.
- [ ] Add MySQL/Postgres memory, outbox, reindex, scope, security, and frontend focused tests; run the `chat` target.

### H — MCP and sandbox runtime

- [ ] Implement HTTPS streamable-HTTP MCP runtime through the shared SSRF transport, authenticated schema snapshots, and reinitialization drift checks.
- [ ] Add capability-gated provider code/computer sandbox plans with immutable policy snapshots, durable approvals, bounded actions, and asset screenshots.
- [ ] Add MCP redirect/proxy/schema tests and sandbox policy/approval focused tests; run the `chat` target.

### I — Frontend run ownership and typed presentation

- [ ] Implement create-then-follow transport with stable idempotency keys, strict SSE framing, replay, bounded reconnect, and authoritative 410 recovery.
- [ ] Add pure parent-scoped run reducer/state ownership, navigation continuity, and temporary-thread opaque session persistence.
- [ ] Replace raw streaming rendering with typed ordered parts, accessible approvals/status, desktop/mobile capability composition, and action affordances.
- [ ] Add deterministic mock transport fixtures and browser/component coverage for every typed part and capability flow.
- [ ] Run frontend check, build, design target, and required desktop/mobile browser proof.

### Deferred rollback cleanup

- [ ] After an observed rollback window, perform A4a canonical-only cutover while retaining legacy columns and record the reverse-backfill cutover timestamp.
- [ ] After a second rollback window, perform A4b legacy column/fallback removal with A4a as the only binary rollback target.

### Existing separate external API-key work — intentionally not this scope

- [ ] Add external API-key migration, encrypted key service, owned CRUD, request authentication, OpenAI-compatible endpoint, and Redis rate limits.
- [ ] Add external usage statistics, wallet APIs, monthly quota scheduler, SaaS fields, and corresponding focused tests.

### Final verification and release decision

- [ ] Run required MariaDB migration/run integration tests without skips.
- [ ] Run required Redis/PostgreSQL/pgvector integration tests without skips.
- [ ] Run API/worker private-S3/ClamAV runtime smoke with all capability scenarios.
- [ ] Run `npm run test:all` and `npm run lint:backend` in that order after focused and runtime proof pass.
- [ ] Complete the security/audit/ownership/secret/log hygiene checklist and preserve unrelated work.
- [ ] Archive only when this scope is evidence-backed complete and no intentionally separate unchecked task requires the change to stay active.
