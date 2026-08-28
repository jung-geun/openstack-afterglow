## Why

Static Kubernetes Ingress manifests route root-scoped MCP OAuth discovery URLs to SvelteKit instead of FastAPI. As a result, RFC 9728/RFC 8414 discovery receives a login redirect or application shell rather than backend metadata.

## What Changes

- Lock FastAPI root-scoped route and static Ingress coverage with a backend regression test.
- Route `/.well-known` to `backend:8000` in all static Ingress host rules that route `/api` there.
- Route the API-subdomain `/v1` path to Lumen on port `8012`, matching the OpenAI/Anthropic-compatible service and Helm template.
- Prevent the frontend SPA fallback from returning a 200 application shell for a misrouted `/.well-known` request.
- Correct the deployment guide's copy-pasteable Ingress path map and frontend port.

## Capabilities

### New Capabilities

- Static Ingress coverage verification for backend root-scoped routes.

### Modified Capabilities

- MCP OAuth discovery is reachable through the static Kubernetes Ingress manifests.
- API-subdomain `/v1` is served by Lumen instead of an unmounted Afterglow backend path.

## Impact

Changes static deployment manifests, the Helm Ingress template, frontend fallback routing, backend/frontend tests, test-target registration, and the deployment documentation. No Kubernetes Lumen Deployment or Service is introduced; operators using the API-subdomain rule must provide the Lumen service.
