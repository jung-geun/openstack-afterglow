## Phase 48 — Frontend 공통 패턴 추출

### Phase 48a — SWR 헬퍼 추출

- [x] `frontend/src/lib/utils/swr.svelte.ts` 신규 생성 (`createSwr` 팩토리)
- [x] `volumesController.svelte.ts` 인라인 swrGet/swrSet → `createSwr` import
- [x] `dashboard/network/networks/+page.svelte` 인라인 swrGet/swrSet → `createSwr` import
- [x] `dashboard/compute/instances/+page.svelte` 인라인 swrGet/swrSet → `createSwr` import
- [x] `dashboard/file-storage/+page.svelte` 인라인 swrGet/swrSet → `createSwr` import
- [x] npm run check 62 errors (기존과 동일, 신규 없음)
- [x] npm run test 7 failed / 215 passed (기존과 동일, 신규 없음)

### Phase 48b — Controller 추출

- [x] `admin/database-instances/[id]` → `adminDatabaseInstanceDetailController.svelte.ts`
- [x] `dashboard/network/loadbalancers/[id]` → `networkLoadbalancerDetailController.svelte.ts`
- [x] `dashboard/loadbalancers/[id]` → `loadbalancerDetailController.svelte.ts`
- [x] `admin/quotas` → `adminQuotasController.svelte.ts`
- [x] `admin/groups` → `adminGroupsController.svelte.ts`

### Phase 48c — 인라인 타입 통합

- [x] `dashboard/topology/+page.svelte` 5개 인라인 타입 → `lib/types/topology.ts`
- [x] `Network`/`SubnetDetail` 중복 2곳 → `lib/types/networks.ts`
- [x] `Project`/`ProjectMember` → `lib/types/project.ts` (신규)
- [x] `PagedResponse<T>` → `lib/types/resources.ts` (기존)
- [x] `SecurityGroupRule`/`SecurityGroup` → `lib/types/securityGroup.ts` (신규)
- [x] `QuotaItem`/`ManilaFileQuota` → `lib/types/quotas.ts` 확장

### Phase 48d — ConfirmDialog 추출

- [x] `lib/components/ui/ConfirmDialog.svelte` 신규 (ESC 닫기 포함)
- [x] `lib/stores/confirm.svelte.ts` 신규 (`confirmDialog()` Promise<boolean>)
- [x] `+layout.svelte`에 `<ConfirmDialog />` 마운트
- [x] routes 31개 파일 42곳 `confirm()` → `await confirmDialog()` 치환
- [x] Phase 48b controller 3개 내부 `confirm()` 동일 치환

### Phase 48e — Modal/FormModal 추출

- [x] `lib/components/ui/Modal.svelte` 신규 (백드롭 + ESC 닫기)
- [x] `lib/components/ui/FormModal.svelte` 신규 (Modal 래핑, submit/cancel 슬롯)
- [x] `admin/floating-ips/+page.svelte` 인라인 백드롭 2곳 → `<Modal bind:open>` 교체
- [x] `admin/drover/templates/+page.svelte` 인라인 백드롭 1곳 → `<Modal>` 교체
- [x] npm run check 62 errors (기존과 동일)
- [x] npm run test 7 failed / 215 passed (기존과 동일)

### Phase 48 — 180줄 잔존 파일 예외 처리 (architect 검증 완료)

다음 5개 파일은 Phase 48b 명시 스코프(5개)에 포함되지 않았으며, architect 검토 결과 controller 추출 ROI 부족으로 **의도적으로 제외**:

| 파일 | 줄수 | 제외 사유 |
|---|---|---|
| `admin/volumes/+page.svelte` | 200 | modal 합성 컨테이너, template 98줄 고정 — 추출 가치 < 비용 |
| `admin/orphans/+page.svelte` | 193 | bind:selected 양방향 바인딩 4개, 추출 시 wrapping 오버헤드 |
| `admin/ports/+page.svelte` | 193 | Phase 49+ 후속 분리 검토 대상 |
| `dashboard/network/security-groups/+page.svelte` | 187 | bind:ruleForm 양방향 바인딩, Phase 49+ 검토 |
| `dashboard/network/networks/[id]/+page.svelte` | 185 | Phase 49+ 후속 분리 검토 대상 |

