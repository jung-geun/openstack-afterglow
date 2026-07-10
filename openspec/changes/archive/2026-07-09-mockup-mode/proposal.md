# Mockup Mode

## Goal
Provide a frontend-only mockup mode for tutorial, marketing, and screenshot workflows without requiring production admin login or sending real API mutations.

## Scope
- Add mockup query/cookie SSR handshake for `?mockup=tutorial`, `?mockup=admin`, and `?mockup=off`.
- Keep mock auth persistence separate from real `afterglow_auth` and `afterglow_session`.
- Support the limited route set: `/`, `/select-project`, `/dashboard`, `/dashboard/compute/instances`, `/dashboard/drover`, `/dashboard/network/topology`, and `/admin`.
- Provide deterministic frontend fixtures and local state transitions for supported reads and core mutations.
- Filter chrome/navigation and show a visible mockup banner.

## Non-goals
- No mock support for unsupported dashboard/admin subroutes, object storage, terminals/shells, Notion test pages, or VM create wizard.
- No backend changes and no real API side effects in mock mode.
