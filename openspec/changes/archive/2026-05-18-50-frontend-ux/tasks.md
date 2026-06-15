## Phase 49 — Frontend 후속 리팩토링 (UX 일관성 + 구조 개선)

### Phase 49a — confirm() 잔존 39건 confirmDialog 치환

- [x] lib/stores 14개 파일 (instanceDetail, dbInstanceDetail, loadBalancerDetail, routerDetail, fileStorageDetail, volumeDetail, volumesController, networkDetail, objectBrowser, k3sClusterDetail, imageDetail, k3sClusterListController, containerDetail, imagesController) confirm() → await confirmDialog()
- [x] lib/components 4개 (K3sClusterConfigMapsCard, K3sClusterSecretsCard, KeypairsSection, SystemAdminTable) confirm() → await confirmDialog()
- [x] grep confirm() 0건 확인
- [x] npm run check 62 errors baseline 유지
- [x] npm run test 7 known failures 외 회귀 없음

### Phase 49b — alert() 128건 toast 교체

- [x] lib/stores 14개 + lib/components 2개 alert() → toast.error/warning/success 치환
- [x] routes/ 29개 파일 alert() → toast.error/warning/success 치환
- [x] grep alert() 0건 확인
- [x] npm run check 62 errors baseline 유지
- [x] npm run test 7 known failures 외 회귀 없음

### Phase 49c — legacy dashboard/loadbalancers/new/ 삭제

- [x] +page.svelte + +page.server.ts 삭제 (진입 link 0건 사전 확인)
- [x] npm run check 62 errors baseline 유지

### Phase 49d — resources.ts 도메인 분리

- [x] 7개 중복 이름 단일 source 통합 (Network/NetworkDetail/SubnetDetail → networks.ts, SecurityGroup → securityGroup.ts, Quotas → quotas.ts DashboardQuotas, QuotaItem/PagedResponse → 각 도메인)
- [x] common.ts/compute.ts/volume.ts/loadbalancer.ts/database.ts/fileStorage.ts 도메인 파일 분리
- [x] 143개 import 업데이트 — from '$lib/types/resources' 잔존 0건

### Phase 49e — 11개 Detail store controller 컨벤션 정렬

- [x] 파일명 xxxDetailController.svelte.ts, factory createXxxDetailController
- [x] loadBalancerDetail 신·구 공존 해소

### Phase 49f — GlobalTopology.svelte 678줄 내부 분해

- [x] lib/components/topology/ 신규 (topologyHelpers.ts, topologyDerivedController.svelte.ts, TopologyHeader.svelte, TopologySidebar.svelte)
- [x] GlobalTopology.svelte ≤ 250줄 (241줄)

---

