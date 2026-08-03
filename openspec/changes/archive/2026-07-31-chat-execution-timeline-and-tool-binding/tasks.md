## Implementation Tasks

- [x] Extend durable run events and history projection with ordered, display-safe execution activity per assistant turn.
- [x] Replace lossy assistant/tool collapse with an execution-aware display projection that retains reasoning and category boundaries.
- [x] Upgrade the execution timeline to a closed-by-default, accessible disclosure with nested reasoning and tool-category details.
- [x] Add `preloaded` / `on_demand` persistence, migration, API validation, and administrator controls for global MCP and custom tools.
- [x] Add compact catalog and explicit loader bindings; preload only builtins and administrator-approved eager extensions.
- [x] Revalidate frozen selection, owner scope, active/configuration state, and MCP credentials before deferred binding and dispatch.
- [x] Add backend and frontend regression coverage for persistence, authorization, policy, timeline grouping, and disclosure behavior.
- [x] Run focused tests, exercise the browser flow, and archive the completed change.
