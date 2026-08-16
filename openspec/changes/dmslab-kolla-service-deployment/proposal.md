# Standalone service API contracts and DMSLab deployment

## Goal
Make Drover, Lumen, Waygate, and Palimpsest independently owned services with runtime-authoritative API contracts. Afterglow remains the dashboard/BFF: it discovers project-scoped service endpoints, forwards caller authority, and contains no duplicate service implementation or image build stage.

## Scope
- Treat `openstack-afterglow/drover`, `openstack-afterglow/lumen`, `openstack-afterglow/waygate`, and `openstack-afterglow/palimpsest` as the only service source repositories.
- Make each FastAPI `/openapi.json` describe its real authentication, discovery, health, request, response, and asynchronous-operation contract; focused tests prevent runtime schema drift.
- Keep service-native HTTP under `/v1`, use project-scoped Keystone tokens for user/API calls, and keep machine-only callback credentials scoped to their owning service.
- Make each shipped SDK/client use only service-native routes and payloads. Afterglow preserves browser compatibility paths under `/api/v1` at its BFF boundary.
- Finish the dedicated Palimpsest Hub API/worker and direct client boundary already present in the Palimpsest repository, including safe resumable uploads.
- Migrate Afterglow Hub callers to the catalog-discovered Palimpsest service and remove embedded Hub API, worker, persistence ownership, service source copies, and service image stages after caller cutover.
- Stop the Afterglow CI/test workflow from validating dead in-repository service copies. Each standalone repository owns its service and SDK tests; Afterglow tests only BFF/client integration.
- Configure Kolla roles with immutable standalone image references and deploy only the custom service roles without changing unrelated OpenStack services.

## Constraints
- Work only from each repository's `dev` branch; publish only committed, verified source.
- Preserve the existing Kolla inventory, services, passwords, and databases. No `destroy`, global `reconfigure`, or unscoped Kolla deployment.
- Do not expose or commit secrets.
- Browser compatibility paths remain stable at Afterglow; native service specifications must not advertise Afterglow-owned paths.
- Palimpsest authorization, immutable blob digests, project isolation, and upload offset integrity remain fail-closed across the boundary.
- Public Drover and Waygate catalog records remain unchanged unless a separately verified ingress change is required.

## Risks
- The existing service SDKs are handwritten, so route/payload tests must bind them to the runtime OpenAPI rather than relying on duplicated documentation.
- Lumen has separate Keystone-user and API-key surfaces plus durable SSE URLs; confusing native and BFF paths breaks resumable chat runs.
- Palimpsest Hub exists as a separate API/worker but its former HMAC-only auth, old Afterglow client prefix, and missing upload-offset endpoint make the current client/service pair unusable.
- Removing monorepo service trees before their repository tests and immutable dependency pins pass would make the required repository gate falsely green.
- The existing DMSLab catalog endpoints do not prove public DNS/proxy reachability; deployment remains scoped and fail-closed until standalone images, catalog discovery, and endpoint routing all pass.
