## Implementation Tasks

### Baseline and shared request contract

- [x] Record three-run cold-navigation baseline for `/admin/services`, `/admin/libraries`, `/admin/ports`, `/dashboard/compute/instances`, `/dashboard/object-storage/buckets`, and `/dashboard/network/topology` with identical environment metadata, initial `/api/v1/` count, request overlap, and primary-loading-clear median.
- [x] Add canonical normal/refresh URL-family construction, ordinary JSON GET in-flight sharing, bounded explicit prefetch, structured-clone isolation, scope epochs, auth-safe failure behavior, and targeted invalidation in `frontend/src/lib/api/client.ts`.
- [x] Invalidate captured scope before/after all shared mutations, progress uploads, `postSse`, and `streamK3sProgress`; add mock profile revision/reset fencing.
- [x] Scope and coalesce `projectNames` and Grafana context by token/project/mock revision; invalidate project names on admin project create/edit/delete.

### Duplicate initial refresh ownership

- [x] Apply `invokeOnMount: false` only to verified same-loader duplicates in the table below; preserve distinct logs/traffic/health/core loaders.
- [x] Make ActivityLogTable reactive loading the sole initial owner with 250 ms abortable filter debounce; defer ObjectBrowser periodic refresh until its initial current/meta round.

### Administrator loading graphs

- [x] Load only active/intent service category and refresh only the active category; show idle count as an em dash.
- [x] Use normal cached initial library GETs while retaining refresh-mode manual/poll/mutation rounds.
- [x] Split admin project/member and system-admin/policy boundaries; parallelize quota/GPU and group member/candidate loaders.
- [x] Release admin user activity independently from the sequential marker walk; reuse scoped project names in ports.
- [x] Add scoped/cancellable next-marker prefetch to admin images, instances, ports, projects, and volumes.

### User loading graphs and intent preload

- [x] Start instance list and metrics summary together; make shared instance detail primary/ancillary loaders concurrent with independent commits and generation fencing.
- [x] Split object-storage bucket/trash/account, usage stats/trend, and notification GET/read-mark boundaries.
- [x] Defer hidden K3s detail tabs and add 250 ms abortable library search.
- [x] Prefetch named create/restore catalog GETs on enabled pointer/focus intent without preloading mutations or SSE.
- [x] Prefetch user topology instance/router core detail after 150 ms hover/focus with leave/blur/scope cancellation.

### Verification and completion

- [x] Add API/cache/mock/project-name/auto-refresh/Button/Pagination behavioral tests from the approved execution plan.
- [x] Add deferred-promise route/controller tests for concurrency, partial release, stale fencing, tab deferral, pagination reuse, topology cancellation, and representative catalog intent.
- [x] Run all named frontend test targets and fix failures.
- [x] Repeat the six-route browser baseline under identical conditions; require lower/deferred request count, overlap for independent requests, and no median primary-loading regression.
- [x] Run `npm run check`, `npm run build`, `npm run test:all`, and `npm run lint:backend` with the approved dirty-baseline exception only for unchanged pre-existing check diagnostics.
- [x] Mark all tasks complete and archive with `openspec archive frontend-loading-performance --skip-specs --yes`.

## Verified duplicate loader table

| Exact path | Auto-refresh callback / explicit owner | Initial endpoint signature(s) | Intentionally distinct retained work | Expected before first interval |
|---|---|---|---|---:|
| `frontend/src/routes/admin/containers/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/all-containers` | — | 1 |
| `frontend/src/routes/admin/database-instances/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/database-instances?all_projects=true` | — | 1 |
| `frontend/src/routes/admin/drover/+page.svelte` | `load` / `onMount → load` | `GET /api/v1/admin/k3s-clusters` | `projectNames.load` | 1 |
| `frontend/src/routes/admin/drover/templates/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/k3s-cluster-templates` | — | 1 |
| `frontend/src/routes/admin/flavors/+page.svelte` | `load` / `onMount → load` | `GET /api/v1/admin/flavors?limit=999` | `projectNames.load`; click-only detail | 1 |
| `frontend/src/routes/admin/floating-ips/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/all-floating-ips` | modal-intent `GET /api/v1/admin/all-networks` | 1 |
| `frontend/src/routes/admin/groups/+page.svelte` | `ctrl.load` / `onMount(ctrl.load)` | `GET /api/v1/admin/groups` | expanded members/candidate users | 1 |
| `frontend/src/routes/admin/hypervisors/+page.svelte` | `load` / `onMount → load` | `GET /api/v1/admin/hypervisors`; `GET /api/v1/admin/gpu-hosts` | `projectNames.load`; click-only detail | 1 each |
| `frontend/src/routes/admin/images/+page.svelte` | `load(curMarker)` / `onMount → load()` | `GET /api/v1/admin/images?limit=…[&marker/search/visibility]` | `projectNames.load`; next-marker intent | 1 |
| `frontend/src/routes/admin/instances/+page.svelte` | `load(marker)` + `loadTimeseries` / `onMount` | `GET /api/v1/admin/all-instances?limit=…[filters]`; `GET /api/v1/admin/timeseries/instances?range=…` | hosts, health, project names | 1 each |
| `frontend/src/routes/admin/loadbalancers/+page.svelte` | `fetchLoadbalancers` / `onMount` | `GET /api/v1/admin/all-loadbalancers` | selection-driven detail | 1 |
| `frontend/src/routes/admin/networks/+page.svelte` | `loadNetworks` + `loadTimeseries` / `onMount` | `GET /api/v1/admin/all-networks`; `GET /api/v1/admin/timeseries/networks?range=…` | — | 1 each |
| `frontend/src/routes/admin/object-storage/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/object-storage?all_projects=true&include_quarantine=true&include_trash=true&include_deleted=true` | — | 1 |
| `frontend/src/routes/admin/orphans/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/orphans?min_age_days=…` | cleanup mutation and follow-up | 1 |
| `frontend/src/routes/admin/ports/+page.svelte` | `load(marker)` / `onMount → load` | `GET /api/v1/admin/all-ports?limit=…[&marker/project_id]` | networks; scoped `projectNames.load`; next-marker intent | 1 |
| `frontend/src/routes/admin/projects/+page.svelte` | `autoRefreshLoad` / `onMount → load()` | `GET /api/v1/admin/projects?limit=…[&marker]` | next-marker intent | 1 |
| `frontend/src/routes/admin/roles/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/roles` | — | 1 |
| `frontend/src/routes/admin/routers/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/all-routers` | modal-intent external networks | 1 |
| `frontend/src/routes/admin/services/+page.svelte` | `loadAll(true)` / `onMount → loadAll()` | `GET /api/v1/admin/services?category=…` | inactive category tab intent | 1 active category |
| `frontend/src/routes/admin/system-admins/+page.svelte` | `load` / `onMount(load)` | `GET /api/v1/admin/identity/system-roles`; `GET /api/v1/admin/identity/security-policy` | independent policy state | 1 each |
| `frontend/src/routes/admin/topology/+page.svelte` | `ctrl.fetchTopology` / token effect | `GET /api/v1/admin/topology` | project names; separate traffic controller | 1 |
| `frontend/src/routes/admin/topology/+page.svelte` | `ctrl.loadTraffic` / token effect | `GET /api/v1/networks/topology/traffic?all_projects=true` | topology graph | 1 |
| `frontend/src/routes/admin/users/+page.svelte` | `loadAll` + `loadActivity` / `onMount` | marker walk `GET /api/v1/admin/users?limit=100[&marker]`; `GET /api/v1/admin/users/activity?limit=10` | marker pages stay sequential; activity commits independently | 1 per request/page |
| `frontend/src/routes/admin/volumes/+page.svelte` | `load` + timeseries + status / `onMount` | `GET /api/v1/admin/all-volumes?limit=…[filters]`; timeseries; status-summary | `projectNames.load`; next-marker intent | 1 each |
| `frontend/src/routes/dashboard/compute/images/+page.svelte` | `ctrl.fetchImages` / project effect | `GET /api/v1/images` | — | 1 |
| `frontend/src/routes/dashboard/compute/instances/+page.svelte` | `fetchInstances` / project effect | `GET /api/v1/instances`; `GET /api/v1/instances/metrics-summary-batch` | metrics remains best-effort, independently committed | 1 each |
| `frontend/src/routes/dashboard/compute/keypairs/+page.svelte` | `fetchKeypairs` / project effect | `GET /api/v1/keypairs` | — | 1 |
| `frontend/src/routes/dashboard/containers/instances/+page.svelte` | `fetchContainers` / project effect | `GET /api/v1/containers` | detail logs auto-refresh is distinct | 1 |
| `frontend/src/routes/dashboard/containers/clusters/+page.svelte` | `fetchClusters` / project effect | `GET /api/v1/clusters` | create-form templates catalog | 1 |
| `frontend/src/routes/dashboard/database/backups/+page.svelte` | `fetchBackups` / project effect | `GET /api/v1/database-instances/backups` | restore instances/flavors catalogs | 1 |
| `frontend/src/routes/dashboard/database/instances/+page.svelte` | `load` / project effect | `GET /api/v1/database-instances` | — | 1 |
| `frontend/src/routes/dashboard/my-resources/+page.svelte` | `load` / project effect | `GET /api/v1/user-dashboard/summary` | — | 1 |
| `frontend/src/routes/dashboard/network/networks/[id]/+page.svelte` | `fetchNetwork(id)` / route effect | `GET /api/v1/networks/{id}` | subnet actions | 1 |
| `frontend/src/routes/dashboard/network/loadbalancers/[id]/+page.svelte` | `ctrl.fetchAll` / project effect | LB core, listeners, pools, conditional status GETs | selected-pool members | 1 each |
| `frontend/src/routes/dashboard/network/routers/[id]/+page.svelte` | `fetchRouter` / project effect | `GET /api/v1/routers/{id}` | interface/gateway networks catalog | 1 |
| `frontend/src/routes/dashboard/network/topology/+page.svelte` | `fetchTopology` / project effect | `GET /api/v1/networks/topology` | distinct traffic auto-refresh | 1 |
| `frontend/src/routes/dashboard/object-storage/buckets/+page.svelte` | `load` / project effect | bucket, trash-container, account GETs | — | 1 each |
| `frontend/src/routes/dashboard/secrets/+page.svelte` | `fetchAll` / project effect | secrets, secret-containers, secret-orders, effective quota GETs | ACL/consumer/payload intent | 1 each |
| `frontend/src/routes/dashboard/topology/+page.svelte` | `fetchTopology` / token effect | `GET /api/v1/networks/topology` | — | 1 |
| `frontend/src/routes/dashboard/volumes/+page.svelte` | `ctrl.fetchAll` / project effect | volumes, optional snapshots, auto-backup configs, quotas | controller fan-out remains independent | 1 each |
| `frontend/src/routes/dashboard/volumes/[id]/+page.svelte` | `fetchVolume(id)` / route effect | `GET /api/v1/volumes/{id}` | dependent attachment-name instance GETs | 1 core |
| `frontend/src/routes/dashboard/volumes/backups/+page.svelte` | `fetchBackups` / project effect | `GET /api/v1/volumes/backups` | restore-form volumes catalog | 1 |
| `frontend/src/routes/dashboard/volumes/snapshots/+page.svelte` | `fetchSnapshots` / project effect | `GET /api/v1/volume-snapshots` | create-form volumes catalog | 1 |
| `frontend/src/lib/stores/dbInstanceDetailController.svelte.ts` + `DbInstanceDetailPanel.svelte` | `loadAll` / panel effect | core, databases, users, optional backups, conditional flavors, floating IPs, optional auto-backup GETs | subresource mutations | 1 each |
| `frontend/src/lib/components/K3sClusterDetailPanel.svelte` | cluster+health callback / ID effect | admin/user cluster core GET | ACTIVE-only health/namespaces remain distinct | 1 core; 1 active ancillary |
| `frontend/src/lib/components/admin/ActivityLogTable.svelte` | `load` / reactive filter effect | `${endpoint}?limit=50[filters]` | click-only `before_id` load more | 1 |
| `frontend/src/lib/components/ObjectBrowser.svelte` (admin mode) | `s.load({silent:true})` / store effect | objects listing GET | initial metadata GET; user `refreshAll` excluded | 1 objects; 1 metadata |

Excluded as genuinely non-duplicate ownership: instance-detail polling already uses `invokeOnMount: false`; container-detail log polling differs from its core loader; user topology traffic differs from graph loading; user-mode ObjectBrowser `refreshAll` differs from initial current/meta loading.



## Pre-change baseline

Environment: 2026-07-18 local SvelteKit dev server at `http://127.0.0.1:5173`, Chromium 839×988, tutorial mock profiles (`admin`/`on`), configured local backend at `http://127.0.0.1:8000`. Each sample navigated away, cleared the instrumentation log, then used `page.goto(..., waitUntil: "domcontentloaded")` to remount the target route. A temporary, subsequently removed `api.get` probe wrote `{ path, performance.now() }` to `sessionStorage`; `/admin/ports` was temporarily admitted to the admin mock route allowlist for measurement and restored immediately afterward. The tutorial transport resolves calls in-process, so `PerformanceResourceTiming` recorded zero real `/api/v1/` network entries. Counts below are measured browser-side API dispatches, including two shared layout requests.

| Route | Initial `/api/v1/` dispatch count (3 runs; median) | Independent route requests overlap before first settles? | Primary loading clear (ms, 3 runs; median) |
|---|---:|---|---|
| `/admin/services` | `11, 11, 11`; **11** (`9` route + `2` layout) | Yes, nine category calls shared the same start turn | `102, 89, 90`; **90** |
| `/admin/libraries` | `9, 9, 9`; **9** (`7` route + `2` layout) | Yes, seven `Promise.allSettled` loaders | `252, 95, 108`; **108** |
| `/admin/ports` | `6, 6, 6`; **6** (`4` route + `2` layout) | Yes, ports/projects/networks started together; project names dispatched twice | `98, 83, 82`; **83** |
| `/dashboard/compute/instances` | `4, 4, 4`; **4** (`2` route + `2` layout) | **No**; metrics started only after the list settled | `131, 121, 105`; **121** |
| `/dashboard/object-storage/buckets` | `5, 5, 5`; **5** (`3` route + `2` layout) | Yes, bucket/trash/account started together | `118, 110, 88`; **110** |
| `/dashboard/network/topology` | `3, 3, 3`; **3** (`1` route + `2` layout) | No independent route secondary dispatch in the measured round | `113, 103, 113`; **113** |

Primary clear used the visible busy/skeleton set for the first five routes and the settled topology search control for topology, whose graph intentionally contains persistent pulse animation. In this automated mock tab, mount-time auto-refresh callbacks were visibility-gated and did not dispatch consistently; the verified duplicate-loader table below records those source-level owners, while deferred-promise tests are the authoritative overlap/ownership proof. Mock timings are smoke-test baselines, not backend latency measurements.

Pre-edit `npm run check` baseline: exit `1`, **66 errors / 222 warnings / 118 files with problems** across 1,528 files (`artifact://11`; raw command capture `artifact://12`). These are the dirty-tree comparison set for the approved normalized-diagnostic exception; no frontend performance source edit was present when captured.

## Post-change browser comparison

Environment and ready selectors matched the pre-change run. Samples were interleaved across routes so every `page.goto` remounted the target; the temporary `api.get` probe and temporary `/admin/ports` tutorial allowance were removed immediately afterward. Dispatch counts include tutorial/auth layout GETs when those stores dispatched during the sample.

| Route | Initial `/api/v1/` dispatch count (3 runs; median) | Independent route requests overlap before first settles? | Primary loading clear (ms, 3 runs; median) |
|---|---:|---|---|
| `/admin/services` | `2, 2, 2`; **2** (one active category + layout) | Hidden categories deferred; only compute dispatched initially | `94, 80, 87`; **87** |
| `/admin/libraries` | `9, 9, 9`; **9** | Yes, seven route GETs started within 0–1 ms | `82, 90, 90`; **90** |
| `/admin/ports` | `5, 5, 5`; **5** | Yes, ports/project names/networks started within 0–1 ms; duplicate project-name GET removed | `76, 80, 78`; **78** |
| `/dashboard/compute/instances` | `4, 4, 4`; **4** | Yes, list and metrics started in the same millisecond | `102, 97, 101`; **101** |
| `/dashboard/object-storage/buckets` | `5, 5, 5`; **5** | Yes, active/trash/account started within 0–1 ms; active list owns primary loading | `86, 87, 89`; **87** |
| `/dashboard/network/topology` | `3, 3, 3`; **3** | No initial secondary route GET by design; detail remains intent-only | `105, 122, 110`; **110** |

All six medians were unchanged or lower. Initial dispatches fell on services (`11 → 2`) and ports (`6 → 5`); same-count routes gained concurrency or preserved intentional single-owner loading.

## Completion audit addendum

After re-reading the authoritative plan, the completion audit added the remaining deterministic boundary coverage and fixed the gaps it exposed:

- account, active-container, and trash-container loading/error/empty states now settle independently;
- system-admin primary and security-policy errors no longer erase each other;
- admin quota and group member/candidate rounds capture scope generations before committing;
- upload, progress PUT/POST, `postSse`, and `streamK3sProgress` mutation fences have direct warm-cache invalidation tests;
- project detail, system admins, buckets, usage, notifications, K3s tabs/catalogs, image pagination, quota concurrency, instance derivations, and mock-transport warm reuse have deferred-promise coverage.

The authoritative target set passed: **29 test files / 145 tests**. Browser intent proof used a temporary transport-dispatch probe and temporary mock next marker, both removed immediately afterward:

- admin marker keyboard focus produced one speculative `GET /api/v1/admin/all-instances?...&marker=mock-instance-3&cache=true`; clicking after settlement emitted no second matching transport; changing page size emitted a new visible GET and a separately scheduled next-page prefetch;
- topology leave at 100 ms emitted no request; focus past 150 ms emitted one `GET /api/v1/instances/mock-instance-3?cache=true`; opening after settlement emitted no second core GET while the seven ancillary detail GETs loaded normally;
- tutorial mock smoke recorded zero real `/api/v1/` `PerformanceResourceTiming` resources.

Final gates, rerun in the required order:

- `npm run check`: expected dirty-baseline exit `1`, **66 errors / 222 warnings / 118 files with problems**. The baseline and final sets contain the same 198 unique severity/file/message diagnostics after normalizing TypeScript's object-type elision count in the existing `uploadQueue.test.ts` cast message; zero added or removed diagnostics.
- `npm run build`: exit `0`.
- `npm run test:all`: exit `0` — backend **3005 passed / 49 skipped**, integration **200 passed / 12 skipped**, frontend **632 passed**.
- `npm run lint:backend`: exit `0` — Ruff check passed and **480 files** were already formatted.

## Marker-generation blocker resolution

The five marker routes now capture a monotonically increasing load generation, canonical request path, token, project, page size, and route-specific filters before dispatch:

- `admin/images`: search and visibility filters;
- `admin/instances`: host, project, status, and name filters;
- `admin/ports`: project filter;
- `admin/projects`: page size and canonical marker path;
- `admin/volumes`: project, status, and name filters.

Success, error, loading/refreshing finalization, selection retention, `nextMarker`, and idle prefetch scheduling commit only when every captured owner still matches. Destruction increments the generation and cancels private speculation.

Deferred stale-response tests for all five routes resolve the newer page-size request first, then resolve the old request with different data and marker. Every route retains the new data and schedules only the new canonical marker path. The focused marker suite passed **5 files / 9 tests**.

Post-blocker gates:

- `npm run check`: expected baseline exit `1`, **66 errors / 222 warnings / 118 files with problems**; stable normalized diagnostics remain **198**, with zero added or removed.
- `npm run build`: exit `0`.
- `npm run test:all`: exit `0` — backend **3005 passed / 49 skipped**, integration **200 passed / 12 skipped**, frontend **637 passed**.
- `npm run lint:backend`: exit `0` — Ruff check passed and **480 files** were already formatted.

## GPU quota overlap blocker resolution

`loadGpuQuotas()` now clears `gpuQuotaLoading` whenever the current generation owns finalization, regardless of whether that owning round was foreground or background. Background rounds still do not set loading to `true`, but they can safely settle a foreground loading state they superseded.

The regression test starts a foreground GPU request, supersedes it with `{ background: true }`, resolves the stale foreground first, and verifies loading remains pending until the background owner settles it to `false`. The focused controller suite passed **1 file / 2 tests**.

Post-blocker gates:

- `npm run check`: expected baseline exit `1`, **66 errors / 222 warnings / 118 files with problems**.
- `npm run build`: exit `0`.
- `npm run test:all`: exit `0` — backend **3005 passed / 49 skipped**, integration **200 passed / 12 skipped**, frontend **638 passed**.
- `npm run lint:backend`: exit `0` — Ruff check passed and **480 files** were already formatted.