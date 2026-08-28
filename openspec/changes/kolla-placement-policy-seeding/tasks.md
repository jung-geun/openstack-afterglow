## Implementation Tasks

- [ ] Repair missing production availability-zone policies through the system-admin catalog API.
- [ ] Build and deploy an image containing commit `416546ef` or a descendant through the digest-pinned Kolla release flow.
- [x] Add the reusable Kolla runtime-policy seeding task with the protected bootstrap runtime contract.
- [x] Invoke runtime-policy seeding in deploy, reconfigure, and upgrade at the specified lifecycle points.
- [x] Add and run focused resolver, safe-503, and Kolla contract regressions.
- [x] Package the runtime policy importer script into the backend production Docker image and assert it in Kolla contract tests.
- [ ] Run scoped Kolla reconfigure twice and verify seeded then idempotent policy state plus disposable instance creation.
