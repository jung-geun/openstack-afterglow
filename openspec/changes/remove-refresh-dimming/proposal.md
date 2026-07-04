## Why

Periodic auto-refresh currently dims and temporarily blocks interaction for data-display tables/cards even after the initial load. That makes routine background refresh feel like a disruptive loading state.

## What Changes

- Remove frontend-only content-area auto-refresh dimming and interaction blocking
- Preserve periodic refresh behavior and the top refresh control as the visible indicator

## Impact

`frontend/src/lib/components/` and `frontend/src/routes/` tables/cards only. No backend or refresh-timer behavior changes.
