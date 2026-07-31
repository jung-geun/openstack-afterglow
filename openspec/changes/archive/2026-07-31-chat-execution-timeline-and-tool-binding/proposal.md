# Chat Execution Timeline and Tool Binding

## Goal

Keep one assistant response visually coherent while exposing its ordered reasoning and tool work as a compact, inspectable execution timeline; reduce tool-schema prompt cost by binding non-preloaded tools only after the model explicitly requests them.

## Current state

- Durable runs journal reasoning deltas and tool-call boundaries, but conversation history only rehydrates tool cards. `projectMessagesForDisplay()` collapses intermediate assistant/tool turns and discards the ordered reasoning boundaries.
- `context_tool_schemas()` and `v2_tool_bindings()` discover and pass every eligible builtin, custom, selected MCP, and managed schema into each provider call.
- Extension records have no administrator-controlled eager/deferred loading policy.

## Scope

- Persist and project ordered, user-visible execution activity per durable assistant turn: reasoning blocks, catalog lookup, tool loading, and tool invocation/result.
- Render a closed-by-default execution summary within the existing `ChatBubble`; expansion shows a chronological timeline, each reasoning block and each tool category are separately inspectable.
- Add a compact always-bound catalog/loader protocol. It advertises only eligible tool metadata, loads selected deferred tool schemas into the current run, and revalidates frozen extension selection, current ownership, active state, configuration fingerprint, and MCP credential epoch before binding or dispatch.
- Add an administrator-only `preloaded` / `on_demand` policy for global MCP servers and custom HTTP tools. User-scoped extensions remain on-demand and cannot self-escalate.

## Non-goals

- Do not expose hidden provider reasoning, credentials, tool schemas, or tool arguments beyond the existing redaction/display contract.
- Do not weaken existing extension selection, OAuth, SSRF, approval, or frozen-run guarantees.
- Do not add a new assistant bubble or a client-only inference of tool authorization.

## Acceptance criteria

1. A completed response with interleaved reasoning and tool use renders one assistant message with a collapsed execution summary; expansion preserves journal order and nested reasoning/tool details.
2. Tool activity is grouped by server/source category only from server-projected metadata, while individual calls retain elapsed time and details.
3. Deferred tools are absent from the initial provider schema set. The model can inspect the compact catalog, explicitly load eligible tools, then call only those bound for that run.
4. Admins can set global custom/MCP tools to `preloaded` or `on_demand`; user requests cannot set or modify this policy.
5. Every deferred binding and dispatch remains fail-closed against ownership, active/configuration changes, and MCP credential rotation.
6. Backend and frontend regression tests cover ordering, collapsed/nested disclosure, binding policy, and authorization revalidation.
