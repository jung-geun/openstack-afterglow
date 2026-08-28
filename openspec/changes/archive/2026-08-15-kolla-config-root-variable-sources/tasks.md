## Implementation Tasks

- [x] Point installer and uninstaller variable sources at `/etc/kolla/config/afterglow`.
- [x] Remove active documentation and sample references to `/etc/kolla/afterglow`.
- [x] Add contract coverage for the consolidated variable-source paths and absence of the legacy path.
- [x] Run focused Kolla contract checks.
- [x] Run full tests and backend lint.
- [x] Migrate live variable files and loader symlinks without deleting the legacy directory.
- [x] Reconfigure live Afterglow and verify Kolla resolves no variable source under `/etc/kolla/afterglow`.
- [x] Archive the completed change.
