# Tasks

- [x] 1. Make `DESIGN.md` the canonical design rules document and link it from `frontend/README.md` and `AGENTS.md`.
- [x] 2. Normalize `frontend/src/routes/layout.css` token authority and add `frontend/src/lib/design` token assets.
- [x] 3. Extend/add reusable UI primitives under `frontend/src/lib/components/ui` and export them from `index.ts`.
- [x] 4. Migrate representative consumer files to the token-backed primitives without broad restyling legacy pages.
- [x] 5. Add the visual debt guardrail helpers, baseline, and design-system rule tests.
- [x] 6. Add/strengthen UI primitive tests for Button, Alert, Field, ToggleGroup, UsageBar, and StatusChip.
- [x] 7. Run targeted frontend checks and `npm run check`, then update this checklist.

## Verification notes

- [x] Targeted frontend checks passed: `cd frontend && ./node_modules/.bin/vitest run src/lib/design/__tests__/visualDebt.test.ts src/routes/__tests__/designSystemRules.test.ts src/lib/components/ui/__tests__/Button.test.ts src/lib/components/ui/__tests__/Alert.test.ts src/lib/components/ui/__tests__/Field.test.ts src/lib/components/ui/__tests__/ToggleGroup.test.ts src/lib/components/ui/__tests__/UsageBar.test.ts src/lib/components/ui/__tests__/StatusChip.test.ts src/lib/components/__tests__/AutoRefreshControl.test.ts src/lib/stores/__tests__/theme.test.ts`.
- [x] `cd frontend && npm run check` was executed after targeted tests and still fails with repository-wide Svelte/type errors outside this change's modified files (63 errors, 223 warnings observed). The design-system targeted suite passes after replacing raw hex fallbacks in new UI primitives with token-backed CSS variables.
