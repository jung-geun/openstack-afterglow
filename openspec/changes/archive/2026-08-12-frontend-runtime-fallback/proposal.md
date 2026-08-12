# Frontend runtime fallback

## Goal

Keep the browser API origin on the configured public endpoint if the optional frontend runtime configuration is absent or cannot be parsed.

## Scope

- Use `PUBLIC_API_BASE` in frontend configuration fallback construction.
- Include the dedicated frontend configuration in Kolla reconciliation hashing.
- Harden the Kolla contract checks around public-only frontend configuration.
