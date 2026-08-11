# Public HAProxy routes for service APIs

## Why

Drover, Waygate, and Lumen have public endpoint contracts but only internal Kolla HAProxy backends. Their public hostnames therefore fall through the external frontend rather than reaching their service APIs.

## What Changes

- Add optional plugin-owned external HAProxy service entries for Drover, Waygate, and Lumen without changing the existing internal/admin API backends.
- Validate enabled external route hostnames against each service's public endpoint origin and remove stale Kolla fragments/map entries when disabled.
- Configure the DMSLab hostnames `drover.dmslab.re.kr`, `waygate.dmslab.re.kr`, and `lumen.dmslab.re.kr` through the Kolla external TLS frontend.
- Add contract coverage and deploy/reconfigure verification against the external VIP.

## Constraints

- Keep the existing `<service>-api` HAProxy entries internal; public routes are separate `<service>-public` entries.
- Do not modify Kolla stock templates, globals, passwords, or shared HAProxy configuration outside plugin-managed service fragments and external-map blocks.
