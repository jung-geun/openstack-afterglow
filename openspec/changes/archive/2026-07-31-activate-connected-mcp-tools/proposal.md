## Why

A connected, active Notion MCP server is discoverable from the live runtime, but ordinary chat runs freeze an empty MCP selection. The model therefore receives only built-in tools and truthfully reports no MCP tools.

## What Changes

- Treat omitted tool and MCP selections for a non-agent chat run as all active owner-visible extensions.
- Preserve explicit empty selections as an opt-out and preserve agent allowlists.
- Cover the frozen extension snapshot contract so connected MCP tools reach the runtime.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- Default chat runs include active, owner-visible MCP servers and custom tools when tool use is enabled.

## Impact

- Chat completion extension selection and its backend tests.
- No new MCP credentials, transport types, or user-controlled authentication are introduced.
