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

### OpenClaude web-agent adoption track

- [x] Land and verify additive protocol, workspace, and extension-package migrations; retain v1 admission until v2 executor deployment. Evidence: migrations `053`–`056` and `058`, `backend/tests/test_migration_ledger.py`, `backend/tests/test_chat_completions.py`, `backend/tests/test_chat_agent_protocol.py`, `backend/tests/test_chat_code_workspaces.py`, and `backend/tests/test_chat_extension_packages.py`.
- [x] Freeze authorized extension selections, skill provenance, schema/config fingerprints, and stale-selection failure behavior. Evidence: `backend/tests/test_chat_completions.py`, `backend/tests/test_chat_extensions_store.py`, `backend/tests/test_chat_tool_runtime.py`, and `backend/tests/test_chat_run_protocol.py`.
- [ ] Implement v2 policy-aware tool definitions, bindings, JSON-schema dispatch validation, bounded results, effects, and budgets behind the versioned executor.
- [ ] Add bounded context compaction, encrypted checkpoints, and on-demand repository discovery.
- [ ] Implement v2 approval and ask-user pause/resume records, CAS decisions, expiry, replay, and cancellation. LangGraph tool-approval `interrupt()`/`Command(resume=...)` now creates encrypted, HMAC-bound approval records from actual model calls, freezes tool-definition/config/destination identities, requires bounded run-unique call IDs, and rejects binding drift before external mutation dispatch; `ask_user`, mutation previews, and workspace state/fence binding remain incomplete.
- [ ] Implement project-scoped remote Git code workspaces, credentials, workspace runtime calls, writer fences, and assignment APIs.
- [ ] Implement bounded durable child-agent runs with inherited policy, reservations, lineage, and cancellation closure.
- [ ] Implement project-scoped skills, slash commands, declarative extension packages, and hardened MCP discovery/diagnostics.
- [ ] Extend the existing Svelte chat protocol/UI for capability discovery, modes, workspaces, approvals, interactions, tasks, and artifacts.
- Evidence (consumer-mcp-control-plane §1, 2026-07-27): inbound MCP retains SDK `mcp==1.28.1` and disabled `[services].mcp`; it depends on unfinished v2 tool definitions (118), approvals (120), MCP seams (123), and UI (124). No parent task completion is claimed.
- [ ] Complete focused, integration, browser, full-suite, lint, and security verification before archive.

#### Adoption-track verified increments

- [x] Add manifest migrations `053`–`055`, ORM registrations, v1-default execution-version validation, and config/example/Kubernetes parity. Evidence: `backend/tests/test_migration_ledger.py`, `backend/tests/test_chat_run_protocol.py`, `backend/tests/test_chat_completions.py`, `backend/tests/test_generate_k8s.py`.
- [x] Reconcile an auto-created partial live schema with additive migration `056`; verify required columns, tables, indexes, and foreign keys, then restart backend/chat-worker. Evidence: MariaDB schema preflight plus post-apply `MISSING_*=none`, `/api/v1/health` returns `{"status":"ok"}`, and `backend/tests/test_migration_ledger.py`.
- [x] Add strict v2-only tool contracts and frozen argument validation before handler dispatch. Evidence: `backend/tests/test_chat_agent_protocol.py`.
- [x] Add project-scoped remote workspace/Git-credential route contracts, HTTPS-only runtime boundary, allowed-origin validation, and worker reconciliation hooks. Evidence: `backend/tests/test_chat_code_workspaces.py`, `backend/tests/test_chat_code_workspace_api.py`.
- [x] Add independently testable bounded context and child-policy primitives, plus declarative package manifest validation. Evidence: `backend/tests/test_chat_context_manager.py`, `backend/tests/test_chat_subagents.py`, `backend/tests/test_chat_extension_packages.py`.
- [x] Fail closed on MCP secret decryption, freeze per-user credential versions in encrypted run selections, revoke instead of deleting credentials, serialize mutations with `SELECT ... FOR UPDATE`, and revalidate before every MCP discovery/dispatch. Evidence: `backend/tests/test_chat_extensions_store.py`, `backend/tests/test_chat_tool_runtime.py`, `backend/tests/test_chat_completions.py`.
- [x] Redact integration fixture credentials, access/refresh token payloads, and login-response failures from pytest output. Evidence: `backend/tests/test_integration_auth_session.py`.
- [x] Execute `test_mcp_credential_mutations_serialize_version_updates` against the configured disposable MariaDB test database. Evidence: `AFTERGLOW_TEST_DATABASE_URL` using `docker-compose.dev.yaml` completed in `0.40s` with `1 passed`; the disposable MariaDB container and volume were removed afterward.
- [x] Add v2-only owner-scoped approval and ask-user interaction APIs with row-locked CAS resolvers, strict encrypted-journal event contracts, a pending-expiry index (`058`), and worker-side no-client expiry sweeping. Matching inputs are idempotent even after the worker advances; conflicting decisions/responses are rejected; expiry resolves safely; the last pending input queues one wakeup; queued/awaiting-input cancellation resolves pending inputs, preserves streaming deltas, releases a matching temporary thread’s `active_run_id`, and emits a terminal cancellation without provider I/O. Approval resolution events carry deciding-user/timestamp provenance, and old approval journal rows gain that required provenance from their event timestamp on replay. Evidence: `backend/tests/test_chat_run_protocol.py`, `backend/tests/test_chat_contracts.py`, `backend/tests/test_chat_worker.py`, `backend/tests/test_chat_db_integration.py::{test_v2_durable_input_resolution_is_atomic_and_idempotent,test_v2_input_expiry_sweep_skips_v1_rows_and_resumes_without_client,test_v2_queued_cancellation_finalizes_pending_inputs_and_streaming_message,test_v2_queued_cancellation_releases_matching_temp_thread}`, `backend/tests/test_migration_ledger.py`, `frontend/src/lib/api/__tests__/chatContracts.test.ts`.
- [x] Adapt current built-in, custom HTTP, and MCP discovery records into server-only v2 bindings with provider-safe numeric namespaces, strict closed JSON schemas, immutable source/effect definitions, and pre-dispatch validation. The bindings are consumed by the v2 graph executor; full policy budgets and richer tool results remain in parent task 118. Evidence: `backend/tests/test_chat_agent_protocol.py`, `backend/tests/test_chat_graph_v2.py`.
- [x] Wire v2 graph tool classification through `classify_tool_calls -> preview_tool_calls -> await_input -> execute_tools`, fail closed for non-read tools without an explicit no-approval policy, emit a LangGraph interrupt before mutation dispatch, and persist/resume owner-scoped approvals through the durable worker. Evidence: `backend/tests/test_chat_graph_v2.py`, `backend/tests/test_chat_db_integration.py::test_v2_graph_interrupt_persists_hmac_bound_approval_before_resume`.
- [x] Bind model-requested approval dispatches to canonical tool-definition/config/destination identities, include that identity in the encrypted approval HMAC, and reject a changed binding before `Command(resume=...)` can invoke it. Evidence: `npm run test:target -- backend:tests/test_chat_agent_protocol.py`, `npm run test:target -- backend:tests/test_chat_graph_v2.py`.
- [x] Freeze a default v2 run tool-call limit in the encrypted request, count every model-emitted call before dispatch, and return `policy_limit_exceeded` tool results without executing excess calls. Durable replay preserves the failed status, error code, and error projection instead of reporting a success. Evidence: `backend/tests/test_chat_graph_v2.py`, `backend/tests/test_chat_db_integration.py::test_worker_projects_failed_policy_limit_tool_result`.
- [x] Reject missing, empty, oversized, and duplicate v2 model tool-call IDs before approval or dispatch; persist only unique approval calls under the run lock, rolling back the entire interrupt on a duplicate. Evidence: `backend/tests/test_chat_graph_v2.py::test_v2_graph_rejects_duplicate_call_ids_before_any_binding_dispatch`, `backend/tests/test_chat_graph_v2.py::test_v2_graph_rejects_a_tool_call_id_reused_in_a_later_model_turn`, `backend/tests/test_chat_graph_v2.py::test_v2_graph_rejects_pre_interrupt_tool_id_reused_after_approval_resume`, `backend/tests/test_chat_db_integration.py::test_v2_duplicate_approval_interrupt_rolls_back_all_calls`.
- [x] Project each active v2 run’s durable stage/reasoning/tool event journal into an ordered expandable chat execution timeline, including typed tool failures, the backend-shaped `awaiting_input` approval stage, distinct same-index reasoning across successive assistant messages, and delayed prior-turn completions without contaminating the current message’s parts or reveal buffer; restore explicitly selected MCP IDs to the submitted tool policy; and map scoped `@agent` and `/skill` composer suggestions onto existing agent/skill selection contracts. Evidence: `frontend:src/lib/api/__tests__/chatContracts.test.ts`, `frontend:src/lib/api/__tests__/chatRunReducer.test.ts`, `frontend:src/lib/api/__tests__/chatRevealBuffer.test.ts`, `frontend:src/lib/components/chat/__tests__/ChatPanel.test.ts` (“keeps the live bubble on the current message when a prior completion arrives late”), `frontend:src/lib/components/chat/__tests__/ExecutionTimeline.test.ts`, `frontend:src/lib/components/chat/__tests__/ChatInput.test.ts`.
- [x] Replace the initial custom wedge-tail iteration with the documented `ChatBubble` directional-corner primitive at increment 146; no pseudo-element tail remains.
- [x] Promote Daisy-inspired chat anatomy to the token-backed `ChatBubble` primitive: `chat-start`/`chat-end`, role/time metadata, compact directional corner, optional action footer, and end-message multiline/long-token wrapping. `ChatMessage` supplies content/actions only; shared `--chat-message-*` tokens, UI export, design documentation, and primitive/design regression coverage prevent parallel bubble patterns. Evidence: `frontend:src/lib/components/ui/__tests__/ChatBubble.test.ts`, `frontend:src/lib/components/chat/__tests__/ChatWindow.test.ts`, `npm run test:target -- frontend:src/lib/components/ui/__tests__/ChatBubble.test.ts frontend:src/lib/components/chat/__tests__/ChatWindow.test.ts frontend:src/lib/components/chat/__tests__/ChatPanel.test.ts`, `npm run test:target -- design frontend:src/lib/components/ui/__tests__/ChatBubble.test.ts frontend:src/lib/components/chat/__tests__/ChatWindow.test.ts`; browser proof rendered both themes at `http://localhost:3080/chat-bubble-preview` before the temporary preview route was removed and the frontend container rebuilt.

- [x] Add a durable post-response memory-extraction job that uses only the admin-designated small memory model, classifies several encrypted user-memory records by interest/development/habit/preference/general, and applies validated add/update/delete deltas under an owner-project lock. Preserve manual scoped CRUD, queue only completed top-level persistent runs with memory enabled, and prove job idempotency, ownership, malformed-model-output rejection, retry handling, crash-safe remove behavior, and stale-snapshot conflict rejection. Extraction reads the exact completed run’s messages; only project-scoped records are eligible for automatic mutations; update/delete targets carry keyed state fingerprints and are rechecked under lock before mutation. Provider/source/atomic-write failures retry, and job completion is atomic with mutations. Evidence: focused Ruff check plus `backend/tests/test_chat_memory.py`, `backend/tests/test_chat_memory_extract.py`, `backend/tests/test_chat_memory_jobs.py`, `backend/tests/test_chat_memory_run_messages.py`, `backend/tests/test_chat_conversations.py`, `backend/tests/test_chat_run_protocol.py`, and `backend/tests/test_chat_worker.py` (`68 passed`).
- [x] Freeze the v2 default primary-model-turn budget with the tool-call budget; resolve dynamic binding effects before the approval interrupt and revalidate them on resume; honor code-only `workspace_write_mode=auto_edit`; execute only `parallel_safe` effective reads four-wide while committing tool results in call order; and project bounded v2 display/artifact refs into durable tool-result parts. Evidence: focused Ruff check plus `backend/tests/test_chat_graph_v2.py`, `backend/tests/test_chat_agent_protocol.py`, and `backend/tests/test_chat_run_protocol.py` (`40 passed`). Parent task 118 remains open for policy composition and remaining source coverage.
- [x] Freeze a selected v2 agent's narrowing-only execution-policy snapshot across server, role, agent, and execution mode; persist it in encrypted request data and the non-secret capability snapshot; validate it before deriving graph model/tool limits. V1 payloads remain unchanged. Scope agent CRUD/run lookup to the caller's user/project and permit cloning only active public templates or same-project private sources. Evidence: `backend/tests/test_chat_subagents.py`, `backend/tests/test_chat_run_protocol.py`, `backend/tests/test_chat_completions.py`, `backend/tests/test_chat_graph_v2.py`, `backend/tests/test_chat_agents.py`, and `backend/tests/test_chat_agent_store.py` (`90 passed`). Parent tasks 118 and 123 remain open.
- [x] Freeze validated v2 execution-policy limits on temporary-run admission before encrypting the payload. Preserve legacy private agents as clone-only owner templates, and scope hub ownership presentation to the exact user/project so same-user public templates from another project remain cloneable. Evidence: `backend/tests/test_chat_agent_store.py`, `backend/tests/test_chat_agents.py`, and `backend/tests/test_chat_run_protocol.py` (`41 passed`; MariaDB integration regressions in `backend/tests/test_chat_db_integration.py` require `AFTERGLOW_TEST_DATABASE_URL` and were skipped locally). Parent tasks 118 and 123 remain open.
- [x] Freeze v2 direct-effect allowances separately from delegation limits, intersecting role and execution mode before graph preview/approval/dispatch. Role-forbidden calls yield ordered `policy_effect_denied` results without binding I/O. Hub lists only active public templates. Evidence: `backend/tests/test_chat_subagents.py`, `backend/tests/test_chat_graph_v2.py`, and `backend/tests/test_chat_agent_store.py` (`22 passed` for the role-effect slice). Parent task 118 remains open.
- [x] Reconcile the partial live automatic-memory schema: preflight `chat_memories.category`, the category constraint, `chat_memory_owner_locks`, and `chat_jobs` claim index; apply the missing additive clauses from migration `064` without replaying provider calls; then verify memory-enabled chat admission against the configured MariaDB. Evidence: live preflight found only `category`, `chk_chat_memory_category`, and `idx_chat_jobs_kind_claim` absent; migration `064` added all three; the same production-scoped `active_contents_for_run` completed after apply (0 records), and `/api/v1/health` returned `{"status":"ok"}`.
- [x] Normalize automatic reasoning to explicit `none` before the durable provider boundary for OpenAI GPT-5-family tool requests; reject incompatible explicit reasoning-plus-tools admission with a user-actionable 422; and log stream initialization/consumption exceptions before fail-closed provider handling. Evidence: focused completions and graph reasoning tests (`7 passed`), Ruff, and the rebuilt `chat-worker` smoke returned `token` then `usage` for `gpt-5.6-luna` with tools enabled.

- [x] Render durable chat activity as user-facing tasks only: surface named tool/MCP work and approval waits with localized task labels, hide queue/model/stream/persistence lifecycle stages, preserve the full wire/reducer event contract, and retain existing restored tool-card presentation. Evidence: `frontend:src/lib/api/__tests__/chatTaskLabels.test.ts`, `frontend:src/lib/components/chat/__tests__/ExecutionTimeline.test.ts`, `frontend:src/lib/components/chat/__tests__/ChatWindow.test.ts`, `frontend:src/lib/components/chat/__tests__/ChatPanel.test.ts`, `frontend:src/lib/components/chat/__tests__/ChatToolApproval.test.ts`, `frontend:src/lib/design/__tests__/visualDebt.test.ts` (24 passed), and `npm run build`.
- [x] Preserve provider tool-call IDs (including Gemini thought signatures) for assistant/tool messages while deriving a deterministic bounded internal ID for the durable journal, approvals, UI, and database keys. Reject duplicate provider IDs before v2 dispatch. Evidence: `backend/tests/test_chat_graph.py::TestToolLoop::test_long_provider_tool_id_uses_bounded_journal_id_and_is_echoed_to_provider`, `backend/tests/test_chat_graph_v2.py` (`18 passed`), and focused Ruff check/format.



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
