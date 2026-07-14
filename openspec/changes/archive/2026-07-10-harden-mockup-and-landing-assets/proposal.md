## Why

Pre-push review found mockup route/state regressions and unredacted production-like data embedded in public landing screenshots. These can produce broken mock pages, overwrite a selected mock project or effective branding, and expose real-looking users, identifiers, addresses, and infrastructure names through anonymous static assets.

## What Changes

- Replace public landing console screenshots with synthetic, non-sensitive runtime artwork.
- Enforce mock profile route allowlists before normal session handling.
- Preserve mock profile/project selection and runtime branding across mock navigation and exit.
- Complete K3s mock detail, health, and deleted-item fixtures to match consuming UI contracts.
- Add regression tests covering authenticated mock route restrictions, fixture response shapes, and sanitized public asset references.

## Capabilities

### New Capabilities

- 없음.

### Modified Capabilities

- Mockup navigation, profile selection, branding persistence, and K3s detail behavior.
- Public landing product proof media privacy.

## Impact

- `frontend/src/hooks.server.ts`, mockup state/transport, layout, K3s fixture consumers, landing media references, static landing assets, and focused frontend tests.