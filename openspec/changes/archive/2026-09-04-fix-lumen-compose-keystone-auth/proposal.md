## Why

Afterglow browser sessions are valid and refresh successfully, but local extracted Lumen containers run with an empty `KEYSTONE_AUTH_URL` and no service credentials. The compose service stack command uses only `docker-compose.services.env`, while Lumen credential inputs are expected from `.env`; the explicit empty environment mapping then turns every forwarded Keystone token into a Lumen 401.

## What Changes

- Document and enforce the local service-stack command with both `.env` and `docker-compose.services.env` interpolation sources.
- Add explicit `LUMEN_KEYSTONE_*` inputs to `.env.example` and map them to the Lumen API/worker/migration `KEYSTONE_*` settings.
- Add a Compose contract test that prevents the Lumen Keystone URL/admin settings from disappearing or reverting to container loopback defaults.
- Forward the token’s connection project as `X-Project-Id` and a differing verified system-admin logical selection as `X-Target-Project-Id`, rather than asking Lumen to rescope a home token to an unrelated project.
- Populate the developer’s ignored `.env` from the existing `afterglow.conf` OpenStack section without committing credential values, then recreate only Lumen local containers.

## Capabilities

### New Capabilities
- Local extracted Lumen service stack authenticates Afterglow-forwarded Keystone sessions when its explicit service-owned credential inputs are configured.

### Modified Capabilities
- Local Compose startup now requires both documented env files for the full extracted-service profile.

## Impact

`docker-compose.yml`, `.env.example`, `docker-compose.services.env`, service proxy header transformation/tests, local ignored operator state, and the Lumen Keystone principal contract. Production Kolla’s Keystone endpoint remains unchanged.
