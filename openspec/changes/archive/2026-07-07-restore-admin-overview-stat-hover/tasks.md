# Tasks

- [x] 1. Trace why admin overview identity cards lost hover styling.
- [x] 2. Restore hover/focus styling in `StatTile` so linked cards behave like hypervisor/VM cards.
- [x] 3. Add targeted regression coverage.
- [x] 4. Run targeted verification and record results.

## Verification

- [x] `cd frontend && ./node_modules/.bin/vitest run src/lib/components/ui/__tests__/StatTile.test.ts`
- [x] Compiled `frontend/src/lib/components/ui/StatTile.svelte` with Svelte compiler and verified the scoped CSS emits `a:hover > .stat-tile.svelte-*`, `a:focus-visible > .stat-tile.svelte-*`, and no ungated `.stat-tile.svelte-*:hover`.
- `cd frontend && npm run check` was executed and still fails on existing repository-wide Svelte/type errors outside the `StatTile` hover fix path (64 errors, 223 warnings observed; no `StatTile` errors in output).
