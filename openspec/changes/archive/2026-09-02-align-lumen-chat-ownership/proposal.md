## Why

Lumen already owns the durable AI-chat backend, including LiteLLM provider calls, LangGraph/LangChain agent execution, conversations, tools, memory, usage, and replayable streaming. Afterglow now proxies that API for its chat frontend, but it still carries unused AI runtime dependencies, obsolete chat-worker deployment resources, historical product documentation, and an embedded Lumen Kolla role. Those residuals obscure ownership and can deploy a worker entry point that no longer exists.

## What Changes

- Make Lumen identify itself as the AI-chat API and require Lumen-owned configuration and encryption-key names; keep its local console explicitly development/operator-only.
- Publish the updated service and repository-owned `lumen-kolla` wheel with Python 3.11 Kolla compatibility and immutable release artifacts.
- Consume the released `lumen-kolla` wheel from Afterglow and delete Afterglow's embedded Lumen role without fallback.
- Keep Afterglow's authenticated `/api/v1/chat/*` BFF, SSE forwarding, frontend, and delegated MCP control-plane bridge.
- Remove unused LiteLLM/LangChain/LangGraph/provider runtime dependencies and obsolete chat-worker/checkpointer/pgvector deployment inputs from Afterglow.
- Replace stale Afterglow-owned chat API documentation with the Lumen BFF contract and enforce the ownership boundary in tests.

## Impact

Lumen remains the sole AI-chat execution and persistence service. Afterglow becomes smaller and cannot accidentally start or configure a local chat runtime. Existing historical Afterglow SQL migrations remain untouched; this change does not drop or reinterpret deployed data. Production model/provider secrets remain in Lumen, while Afterglow retains only the explicit workload credential needed for delegated MCP calls.
