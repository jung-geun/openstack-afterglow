# Tasks

- [x] Replace stale db target selectors with current `pytest.mark.db` discovery.
- [x] Add local MariaDB compose bootstrap and `npm run test:db`.
- [x] Update DB testing docs, README, and dev-branch CI selector.
- [x] Add runner catalog validation and `--validate` regression coverage.
- [x] Run local MariaDB DB target and focused JS tests.
- [ ] Run clean dev full gates (`npm run test:all`, `npm run lint:backend`) and commit only this patch.

## Verification

- `npm run test:db -- --no-start`: 53 passed.
- `npm run test:target:js`: 5 passed plus complete catalog validation.
- `npm run test:list`: all target selectors validated and listed.
