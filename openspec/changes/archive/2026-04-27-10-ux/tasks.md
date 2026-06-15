## 10. 관리자 UX 개선 (2026-04-27)

### 10.1 관리자 페이지 필터/검색 추가 (volumes, instances, topology)

> **목표**: 관리자 페이지에서 리소스가 많을 때 특정 항목을 빠르게 찾을 수 있는 서버사이드 필터 추가

- [x] `backend/app/api/identity/admin.py` — `list_all_volumes`: `project_id`, `status`, `name` 쿼리 파라미터 추가 (Cinder `name~` substring 매칭)
- [x] `backend/app/api/identity/admin.py` — `list_all_instances`: `status`, `name` 쿼리 파라미터 추가 (Nova `name=.*{re.escape(input)}.*` regex 변환)
- [x] `backend/app/api/identity/admin.py` — `admin_topology`: `TopologyInstance` 빌드 시 `project_id` 포함
- [x] `backend/app/models/storage.py` — `TopologyInstance.project_id: str | None = None` 추가
- [x] `backend/tests/test_admin_filters.py` — **신규** 7개 테스트: volumes(status/project_id/name~), instances(status/name regex/metachar escape), topology(project_id 포함 검증)
- [x] `frontend/src/lib/components/GlobalTopology.svelte` — `TopologyInstance.project_id` 인터페이스 추가 + `projectId` prop 기반 인스턴스 필터링
- [x] `frontend/src/routes/admin/volumes/+page.svelte` — 프로젝트 autocomplete / 상태 select / 이름 검색 필터 UI (서버사이드, 페이지네이션 연동)
- [x] `frontend/src/routes/admin/instances/+page.svelte` — 상태/이름 필터 추가, 기존 클라이언트사이드 프로젝트 필터 → 서버사이드 전환 (`filteredInstances` derived 제거)
- [x] `frontend/src/routes/admin/topology/+page.svelte` — 프로젝트 검색 드롭다운 추가, `GlobalTopology`에 `projectId`/`showAll` props 연결

### 10.2 전체 페이지 자동 새로고침 추가 (기본 ON)

> **목표**: 새로고침 버튼이 있는 모든 페이지/패널에 자동 새로고침 추가. 기본 ON, localStorage 영속, 탭 비활성 시 일시정지, 페이지 성격별 차등 주기

- [x] `frontend/src/lib/utils/autoRefresh.svelte.ts` — **신규**. Svelte 5 rune 기반 hook. `createAutoRefresh(fn, options)`:
  - localStorage에 `autoRefresh.<key>.active` / `autoRefresh.<key>.interval` 영속
  - Page Visibility API: `document.hidden` 시 timer 정지, 탭 복귀 시 즉시 1회 fetch + 재시작
  - `$effect` cleanup으로 timer/listener 자동 해제 (SSR 안전)
- [x] `frontend/src/lib/components/AutoRefreshControl.svelte` — **신규**. 토글 버튼 + 주기 select + 수동 새로고침 버튼 통합 컴포넌트. `PageHeader` actions snippet에 삽입.
- [x] **admin 23개 페이지 적용**:
  - 15s: `instances`, `monitoring`, `services`, `database-instances`, `drover`, `containers`, `object-storage/[name]`
  - 30s: `topology`, `floating-ips`, `routers`, `gpu`, `hypervisors`, `ports`, `networks`, `file-storage`, `volumes`, `images`, `object-storage`
  - 60s: `flavors`, `groups`, `users`, `roles`, `projects`
- [x] **dashboard 5개 페이지 적용**:
  - 10s: `containers/clusters/[id]`
  - 15s: `containers/instances/[id]` (로그 패널)
  - 30s: `topology`, `file-storage/manage`, `object-storage/buckets/[name]`
- [x] `frontend/src/lib/components/InstanceDetailPanel.svelte` — 콘솔 로그 ad-hoc `setInterval` → `createAutoRefresh` 마이그레이션 (15s)
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — 이벤트 ad-hoc `setInterval` → `createAutoRefresh` 마이그레이션 (15s)
- [x] 기존 ad-hoc 자동새로고침 3곳 통합 제거: `admin/services` (`$effect`+setInterval), `dashboard/containers/clusters/[id]` (자체 setInterval+toggleAutoRefresh), `dashboard/file-storage/manage` (AutoRefreshToggle+setInterval)
- [x] 자동 새로고침 fn은 **필터/marker 보존** (현재 페이지 유지), 수동 새로고침은 **기존 필터 리셋** 동작 유지 (의도적 분리)

### 10.3 관리자 볼륨 — 상태 변경 + 명시적 강제삭제 (2026-04-27)

> **목표**: `deleting` / `error_*` 등 비정상 상태 볼륨을 admin이 임의 상태로 전환하거나 명시적으로 강제 삭제할 수 있도록 UI/API 확장

- [x] `backend/app/api/identity/admin.py::delete_volume` — `_ERROR_STATUSES` (`error/deleting/error_*`) 자동 폴백: `reset_status` → 일반 `delete` → `os-force_delete` 3단계 시퀀스
- [x] `backend/app/api/identity/admin.py::force_delete_admin_volume` — **신규** `POST /api/admin/volumes/{id}/force-delete` (status 무관, attached 볼륨은 409)
- [x] `backend/tests/test_admin_volume_delete.py` — **신규** 11개 (자동 폴백 7 + force-delete 4: normal_status, attached_409, already_gone_204, requires_admin_403)
- [x] `frontend/src/routes/admin/volumes/+page.svelte` — `상태초기화` (error 한정) → `상태변경` (모든 볼륨 노출), `error*/deleting` 상태에 한해 `강제삭제` 버튼/rose 경고 모달 추가

---

