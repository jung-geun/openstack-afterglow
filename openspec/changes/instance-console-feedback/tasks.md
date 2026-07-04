# Tasks

- [x] Add dedicated controller state for console URL opening feedback.
- [x] Render loading and error feedback in the instance detail header.
- [x] Add focused frontend tests for the header console feedback states.
- [x] Verify the focused test, frontend type/Svelte check, and project precommit gates if committing.

## Verification Notes

- Focused frontend component test passed: `cd frontend && npm run test -- --run src/lib/components/instance/__tests__/InstanceHeader.test.ts` (3 tests).
- `cd frontend && npm run check` was run and exited nonzero on existing unrelated project diagnostics outside the touched instance header/controller/test files (for example load balancer, database, wizard, layout, and admin routes). This change did not add diagnostics in the touched files.
- Project pre-commit gates were not run because this session did not commit.
