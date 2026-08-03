# Protocol Tool-Policy Guards

## Goal

Prevent v1 from loading Lumen-managed cloud mutations and prevent v2 from exposing or dispatching any tool when the run tool policy disables tools.

## Problem

The bounded tool catalog was shared by v1 and v2. Its on-demand lookup always included managed Lumen registry bindings. V1 executes catalog-loaded bindings directly and has no v2 mutation classification or approval interrupt, so an `external_mutation` binding could bypass the v2 approval boundary. Durable replay could also restore a managed deferred binding into a v1 run. Separately, v2 resolved bindings without checking `ToolContext.tools_enabled`, bypassing the disabled-tool policy used by legacy execution.

## Scope

- Make catalog search and deferred-binding restoration explicitly protocol-aware.
- Permit managed Lumen bindings only in the v2 catalog and replay path, where mutation approval is enforced.
- Keep v1 limited to built-in, preloaded, and on-demand custom/MCP bindings.
- Add v1 regressions proving a managed mutation cannot load, restore, or dispatch.
- Return no v2 bindings when tools are disabled, before any builtin, extension, MCP, or Lumen resolution.
- Add a v2 graph regression proving disabled tools have no schemas and cannot dispatch.

## Non-goals

- Change v2 approval behavior or Lumen registry authorization.
- Alter custom/MCP load-policy behavior.
- Add a v1 approval workflow; managed cloud mutations remain v2-only.
