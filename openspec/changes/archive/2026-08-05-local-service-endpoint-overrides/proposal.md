# Local extracted-service endpoint overrides

## Goal

Allow Afterglow's Docker Compose backend to reach locally started Waygate, Drover, and Lumen services when the connected Keystone catalog has no endpoint entries for those extracted service types.

## Scope

- Preserve Keystone catalog discovery as the default and production integration path.
- Add trusted, validated backend configuration overrides for local service endpoints.
- Apply the Drover override at SDK registration so all existing backend callers use it consistently.
- Configure the local Compose backend to target the extracted service containers.
- Cover catalog-default and override behavior with regression tests.

## Non-goals

- Register Docker-only endpoints in a shared Keystone catalog.
- Change caller token forwarding or bypass extracted-service authorization.
