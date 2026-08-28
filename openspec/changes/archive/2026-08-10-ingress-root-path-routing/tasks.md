## Implementation Tasks

- [x] Add regression coverage for root-scoped FastAPI routes and static Ingress path maps
- [x] Route `/.well-known` to `backend:8000` in each static Kubernetes Ingress manifest
- [x] Route the API-subdomain `/v1` entry to the Lumen service in static and Helm Ingress templates
- [x] Exclude `/.well-known` from the frontend SPA fallback and cover the behavior
- [x] Correct the static Ingress example in deployment documentation
- [x] Run focused route, frontend, and manifest verification
- [x] Run required repository test and backend lint gates
