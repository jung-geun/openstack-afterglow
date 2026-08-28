# Local extracted-service configuration propagation

## Why

The local extracted-service Compose profile routes the backend to local containers, but the services receive empty or localhost Keystone values instead of the configured `afterglow.conf` values. Lumen therefore cannot validate forwarded browser tokens, and Drover/Waygate cannot make authenticated OpenStack calls.

## What Changes

- Make empty service environment values fall back to their mounted TOML configuration without changing non-empty environment precedence.
- Mount the trusted local `afterglow.conf` read-only into extracted services and point Waygate/Drover at it.
- Keep documented service-specific environment overrides and add regression coverage for empty-value fallback.
