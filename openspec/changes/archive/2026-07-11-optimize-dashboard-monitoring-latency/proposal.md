## Why

인증된 대시보드는 이미 여러 요청을 병렬로 시작하지만, 단일 로딩 상태와 미사용·중복 OpenStack/Prometheus 작업 때문에 카드별 진행 상황이 가려지고 첫 카드 및 전체 응답이 느려진다. K3s 전체 목록의 기존 캐시/소스 키 충돌은 별도 무결성 변경으로 유지하되, 대시보드가 해당 경로를 호출하지 않도록 한다.

## What Changes

- 대시보드 요약과 쿼터에 기본 응답 호환성을 보장하는 `overview` 뷰를 추가해 최근 5개 인스턴스와 렌더링에 필요한 쿼터만 조회한다.
- 프로젝트 범위 Prometheus 추세 조회와 읽기 전용·제한된 K3s 통계 엔드포인트를 추가한다.
- 대시보드 프런트엔드를 도메인별 데이터·대기·오류·취소·stale-good 상태와 배치 동기화 상태로 분리한다.
- 회귀 테스트로 요약·쿼터·K3s·메트릭의 오류 경계, 캐시/테넌트 안전성, 병렬 렌더링, 취소/범위/프로젝트 전환을 고정한다.

## Capabilities

### New Capabilities

- Lean dashboard overview summary, quota, K3s-stat, and project-scoped trend contracts.
- Independent dashboard domain loading, synchronization, and stale-data behavior.

### Modified Capabilities

- Dashboard monitoring fetch graph and cards consume lean contracts rather than full instances, notifications, and K3s-list endpoints.

## Impact

- Backend dashboard routes, quota service fallbacks, K3s read-only storage access, and Prometheus query construction.
- Dashboard route, overview components, frontend contracts, mock transport, and focused backend/frontend regression tests.
- Existing full/default dashboard APIs, legacy notification behavior, K3s list/mutation/callback behavior, and prewarm behavior remain unchanged.

## Baseline Evidence

- 2026-07-12 local checkout: `dev` branch with unrelated dirty landing/login/logout/class-diagram paths preserved.
- Local compose has healthy backend (`:8000`), frontend (`:3080`), and Redis; the optional Prometheus profile is not running. Safe unauthenticated health/config probes are available, but no dashboard data probe is safe without a token.
- The protected `GET http://localhost:8000/api/v1/metrics` baseline attempt returned `401`; its 24-hour histogram cannot be safely read without an authenticated administrator session. The current dashboard must not be loaded because it invokes the unsafe K3s full-list route.
- No authenticated staging/log access was supplied. Therefore no baseline duration, payload-byte, OpenStack-call-count, Keystone, or first/last-card numeric claim is available. Post-change results will remain explicitly non-comparative unless an owner supplies a controlled authenticated staging probe. Safe future direct probes are summary, quotas, instances, notifications, and trend only; K3s list remains excluded.
- A delegated focused test command was later found to use the default host Redis through an autouse cache-flush fixture and may have deleted `afterglow:*` cache/session/source keys. It made no tracked-file changes, but it is not valid baseline evidence. No further test or runtime requests will use the default Redis database; all focused verification will set an isolated `REDIS_URL`.

## Post-change Evidence

- Focused backend contracts passed with `REDIS_URL=redis://localhost:6379/15`, covering overview summary/quotas, strict service fallbacks, K3s bounded source reads, project-scoped trend, notification compatibility, and the central 5xx sanitizer's reviewed-detail branch.
- Focused frontend route tests exercise four concurrent enabled requests (three with K3s disabled), summary-first rendering, absence of `/instances`, `/dashboard/notifications`, and `/k3s/clusters`, project fencing, manual/auto priority, range replacement success/failure, stale-good failure, and teardown aborts. Mock transport and design-system guard tests also pass.
- No live authenticated post-change request was issued: staging credentials, MariaDB, and Prometheus remain unavailable, and the local dashboard must not be used as a production comparison source. Therefore there is no valid numeric before/after latency, payload, Keystone, or origin-call claim. An owner-approved disposable staging token is still required for that measurement.
- Final gate: `npm run test:all` with `REDIS_URL=redis://localhost:6379/15` passed — backend unit `2705 passed, 29 skipped`, integration `200 passed, 12 skipped`, frontend `74 files / 450 tests passed`. `npm run lint:backend` then passed with `419 files already formatted`.
- The backend non-integration suite also passed with `REDIS_URL=redis://localhost:6399/15`, confirming the new function-scoped fakeredis fixture keeps ordinary backend tests independent of a running Redis service. Integration remains intentionally run against its configured local services.
