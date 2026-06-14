## 32. K3s 클러스터 SSE 비동기 삭제 (2026-05-13)

### 32.1 동기

- 동기 `DELETE /api/k3s/clusters/{id}` 가 LB/K8s 노드/VM 대기/SG 순차 수행으로 30초 이상 소요.
- 프런트 `client.ts:72` 의 `AbortSignal.timeout(30_000)` 으로 클러스터가 정상 삭제되어도 `TimeoutError: signal timed out` alert 발생.
- Admin 동기 삭제에 LB / K8s 노드 / App Credential cleanup 미포함 → orphan 리소스 위험.

### 32.2 백엔드

- [x] `backend/app/models/k3s.py::K3sProgressStep` — delete 단계 8개 추가
- [x] `backend/app/api/k3s/clusters.py` — `_SSE_HEADERS` 모듈 상수 추출 (생성/삭제 공유)
- [x] `backend/app/api/k3s/clusters.py` — 공유 async generator `_delete_cluster_progress` 추출
- [x] `backend/app/api/k3s/clusters.py` — `POST /api/k3s/clusters/{id}/delete-async` SSE 엔드포인트 신설
- [x] `backend/app/api/k3s/clusters.py` — 기존 `delete_k3s_cluster` 동기 핸들러를 generator 소진형으로 리팩토링 (204 유지)
- [x] `backend/app/api/identity/admin.py` — `POST /api/admin/k3s-clusters/{id}/delete-async` 신설 (user 와 동일 generator)
- [x] `backend/app/api/identity/admin.py` — `delete_admin_k3s_cluster` 동기 핸들러도 generator 소진형으로 리팩토링 + LB/K8s/AppCred 단계 통일

### 32.3 프런트엔드

- [x] `frontend/src/lib/api/k3sSseStream.ts` (신규) — `streamK3sProgress` async generator 유틸 (30초 제한 우회)
- [x] `frontend/src/lib/components/k3sSteps.ts` (신규) — `K3S_CREATE_STEPS`, `K3S_DELETE_STEPS` 상수
- [x] `frontend/src/routes/dashboard/drover/+page.svelte` — `deleteCluster()` SSE 화, 진행 모달 mode 전환 (create/delete)
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — `deleteCluster()` SSE 화, 패널 인라인 progress bar

### 32.4 검증

- [x] `backend/tests/test_k3s_clusters.py` — SSE 테스트 6건 추가 (client.stream + aiter_lines 첫 도입)
- [x] 기존 동기 삭제 테스트 8건 통과 (44개 전체 통과 확인)
- [x] `npm run lint:backend` 통과
- 사용자 브라우저 검증 필요:
  - 클러스터 삭제 클릭 → 단계별 진행 모달 표시 (delete_init → ... → completed)
  - 30초 이상 소요 클러스터도 alert 없이 완료
  - 상세 패널 삭제 → 패널 내 progress bar 표시 → 완료 후 목록 페이지 이동
  - Admin 경로에서도 동일 동작

### 32.5 향후

- 생성 SSE 호출 (`drover/+page.svelte:190-258` 인라인)을 `streamK3sProgress` 유틸로 교체 (별 PR)

