## Implementation Tasks

- [x] Add endpoint-aware numeric-version inheritance to the Drover SDK and cover unversioned, v1, v2, v2.1, project-scoped, malformed, query, fragment, trailing-slash, positional-argument, and absolute-URL cases.
- [x] Add a strict shared Afterglow service URL joiner and use it for HTTP proxy, JSON proxy, machine passthrough, Drover shell WebSocket, and raw Zun requests.
- [x] Preserve direct Drover feature, callback, ownership, authorization, secret, policy mutation, and quota administration failures as required fail-closed responses.
- [x] Make optional dashboard, quota-display, GPU-availability, flavor-filtering, notification, and form-enrichment reads continue with explicit unavailable or safe filtered results.
- [x] Detect GPU entitlement from PCI passthrough aliases, remove the local database gate, validate quota response shape, and perform quota checks before any Cinder, Manila, Neutron, or Nova mutation.
- [x] Cover synchronous, tenant SSE, and admin SSE GPU creation for allow, denial, unavailable Drover, malformed Drover response, nonstandard GPU flavor names, and zero leaked resources.
- [x] Commit and push the Drover fix, pin both Afterglow Drover SDK dependency groups and the lockfile to that immutable commit, and verify focused tests.
- [x] Run `npm run test:all` followed by `npm run lint:backend`, obtain independent code/security review, archive this change, commit, and push `dev`.
- [x] Verify successful Drover and Afterglow GitHub Actions image-build workflows and record immutable image evidence.
