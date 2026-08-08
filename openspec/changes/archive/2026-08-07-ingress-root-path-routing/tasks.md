## Implementation Tasks

- [x] Add failing root-scoped route and Ingress coverage regression test and register its target.
- [x] Route `/.well-known` to the backend in every static Ingress API host rule.
- [x] Route API-subdomain `/v1` to Lumen in static and Helm Ingress templates.
- [x] Preserve frontend 404 behavior for misrouted `/.well-known` discovery requests.
- [x] Correct the deployment Ingress snippet and frontend service port.
- [x] Run focused, rendered-map, full test, and backend lint verification.
