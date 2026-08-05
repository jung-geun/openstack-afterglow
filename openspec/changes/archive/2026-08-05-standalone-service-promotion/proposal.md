# Standalone service promotion prerequisites

## Why
The extracted services still resolve `afterglow-crypto` through a sibling editable path, and their image stages remain only in the monorepo root Dockerfile. A subtree split therefore cannot install or build a service independently.

## What Changes
- Publish `afterglow-crypto` to a resolvable package or Git source.
- Replace sibling-path crypto sources in Waygate, Drover, and Lumen.
- Give each service its own API/worker Dockerfile.
- Verify standalone installation and image targets, then regenerate the split branches.

## Non-goals
- Reconnect Afterglow's backend dependencies to released SDKs.
- Select or create an external source-code host or package registry without its target URL and publishing policy.