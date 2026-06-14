## 78. 인스턴스 운영 UX 6종 개선

### 78.1 인스턴스 일괄 선택/액션 + 상태 전이 자동 가속 새로고침

- [x] `autoRefresh.svelte.ts` — `setBoost(seconds|null)` 추가: 내부 `_boost` 상태로 유효 interval 재정의, `active=false`면 boost 무시
- [x] `instanceStatus.ts` (신규) — `TRANSITIONAL_STATUSES` Set + `isTransitional(status)` 헬퍼
- [x] `InstancesTable.svelte` + `InstanceRow.svelte` — 체크박스 열 + 전체선택 머리글 (36px grid column)
- [x] `routes/dashboard/compute/instances/+page.svelte` — 일괄 액션 바 (시작/종료/삭제 + confirm), 전이 상태 시 boost(4s)
- [x] `AdminInstanceTable.svelte` — 동일 체크박스 패턴 추가
- [x] `routes/admin/instances/+page.svelte` — 관리자 일괄 액션 바 + boost 연결
- [x] `instanceDetailController.svelte.ts` — 상태 전이 시 detailPollAr boost 자동 적용
- [x] `backend/app/api/compute/instances.py` — `POST /api/instances/bulk-action` (action 화이트리스트·max 50·per-id IDOR·부분성공 응답)
- [x] `tests/test_bulk_instance_action.py` — 10종 (화이트리스트·IDOR·부분실패·정상 start/stop/reboot/delete)

### 78.2 차트 백그라운드 새로고침 (새로고침 시 차트 사라지지 않음)

- [x] `routes/admin/instances/+page.svelte` — `loadTimeseries(range, {background})` 분리, 자동 tick에 background:true
- [x] `routes/admin/file-storage/+page.svelte` — 동일 패턴 적용
- [x] `routes/admin/networks/+page.svelte` — 동일 패턴 적용
- [x] `routes/admin/volumes/+page.svelte` — 동일 패턴 적용

### 78.3 Flavor 프로젝트 접근 추가 버튼 피드백

- [x] `FlavorAccessTab.svelte` — `addingId` state + 처리 중 스피너/"추가 중…" + 성공/실패 toast

### 78.4 GPU 진단 엔드포인트 (실 device_id 노출)

- [x] `backend/app/api/identity/admin_gpu.py` — `GET /api/admin/gpu-hosts/raw` (require_admin, 오디오 필터 미적용, vendor_id/device_id/resolved_name/is_audio 노출)
- [x] `tests/test_admin_services_gpu.py` — 비관리자 403, 관리자 200+hosts 키, device_id/resource_class/is_audio 필드 검증 3종

### 78.5 쿼터 카드 소스 전환 + API 중복 정리

- [x] `QuotaUsageCard.svelte` — vCPU/Memory/Storage/FIP/Shares 전부 `/api/dashboard/quotas` 기반으로 전환 (summary 의존 제거)
- [x] `DashboardStatTiles.svelte` — instances_limit→`quotas.compute.instances.limit`, volumes_used/limit→`quotas.storage.volumes.*` 전환
- [x] `vmCreateStore.svelte.ts` — 비관리자 quota 조회를 `/api/dashboard/summary`→`/api/dashboard/quotas`로 전환 (어드민 경로와 동일 패턴)
- [x] `backend/app/api/common/dashboard.py` — `/summary`에서 `compute_limits`/`volume_limits` gather 제거 (OS API 호출 2건 절감), `compute`/`storage` 필드 응답에서 제거
- [x] `frontend/src/lib/types/compute.ts` — `DashboardSummary`에서 `compute`/`storage` 제거
- [x] `tests/test_dashboard.py` — `/summary` 응답 계약 테스트 갱신 (2-item gather, compute/storage 부재 확인)

---

