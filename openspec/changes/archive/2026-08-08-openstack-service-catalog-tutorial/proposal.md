## Why

The dashboard's Drover k3s statistics request can reach Keystone successfully but fails with `EndpointNotFound` because the Drover service has no public RegionOne catalog endpoint. Administrators need a safe, repeatable procedure to register Drover, Lumen, and Waygate with OpenStack and configure their service URLs.

## What Changes

- Add an administrator tutorial for validating, creating, and verifying the three service-catalog entries.
- Document Kolla/HAProxy endpoint requirements, service types, regions, interfaces, and idempotent OpenStack CLI commands.
- Link the tutorial from deployment documentation.

## Capabilities

### New Capabilities

- Administrator service-catalog registration tutorial for extracted Afterglow services.

### Modified Capabilities

- Deployment documentation links operators to the service-catalog recovery and verification workflow.

## Impact

Documentation only. It does not deploy services, create endpoints automatically, or modify Keystone catalog state.
