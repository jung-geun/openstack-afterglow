# Tasks

- [x] Add `announcements`/`announcement_reads` migration + ORM model
- [x] Add admin announcements router (CRUD, require_admin, input whitelist validation)
- [x] Add user-facing announcements router (server-side targeting resolution, read tracking, IDOR-safe)
- [x] Mount routers in main.py (`/api/v1/admin/announcements`, `/api/v1/announcements`)
- [x] Merge announcements into dashboard alerts card (quota alerts + announcements unified)
- [x] Activate header bell icon (unread badge polling + navigation)
- [x] Add notifications inbox page (`/dashboard/notifications`)
- [x] Add admin announcement composer page (`/admin/announcements`)
- [x] Add backend regression tests (CRUD, targeting correctness, IDOR, validation, unread-count)
- [ ] Run required project checks (`npm run test:all`, `npm run lint:backend`) — blocked: unrelated concurrent WireGuard VPN work (uncommitted, same tree) fails `test_no_unexpected_public_routes` and `test_mutation_handlers_have_invalidation`; all announcement-scoped tests pass in isolation (backend 20 passed/13 db-skipped, frontend 450 passed). See proposal notes.
