## Why

The local `afterglow.frontend.conf` contains backend-only authentication, session, security, CORS, GPU, and secret values even though the frontend runtime consumes only a closed browser-safe configuration projection. Keeping unrelated values in this file increases disclosure risk and obscures the frontend contract.

## What Changes

- Retain only fields consumed by `frontend/src/lib/server/config.ts` and represented by `PublicSiteConfig`.
- Keep the current local browser/API origins and public service flags.
- Remove all backend-only sections and secrets, including application secret, session/security policy, CORS, GPU, and GitLab client credentials.
- Preserve `afterglow.frontend.conf` as a machine-local ignored configuration file and exclude that reserved public projection name from backend override discovery.

## Impact

The ignored local `afterglow.frontend.conf`, backend override discovery, its regression coverage, and deployment documentation change. Deployed Kolla configuration is unchanged.
