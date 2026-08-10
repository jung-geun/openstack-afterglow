## Why

MCP OAuth discovery metadata is served by FastAPI at origin-root `/.well-known/oauth-*` paths, but the static Kubernetes Ingress manifests route those requests to the SvelteKit frontend catch-all. MCP clients therefore receive a login redirect or an HTML app shell rather than OAuth metadata.

## What Changes

- Add a backend regression test that snapshots root-scoped FastAPI routes and verifies every static Ingress host serving `/api` also forwards `/.well-known` to `backend:8000`.
- Route `/.well-known` to the backend in all static Kubernetes Ingress manifests.
- Route the API-subdomain `/v1` path to the existing Lumen service and keep the Helm template consistent.
- Preserve a truthful frontend 404 if a discovery request is nevertheless misrouted.
- Correct the copy-pasteable Ingress example in the deployment documentation.

## Capabilities

### New Capabilities

- `ingress-root-path-routing`: Static Kubernetes Ingress deployments correctly route root-scoped MCP OAuth discovery requests to FastAPI.

### Modified Capabilities

- `deployment-ingress-documentation`: The documented static Ingress path map reflects production service names and ports.

## Impact

Changes affect static Kubernetes manifests, the Helm Ingress template, frontend fallback behavior, deployment documentation, and focused backend/frontend regression coverage. No FastAPI endpoint contract changes.
