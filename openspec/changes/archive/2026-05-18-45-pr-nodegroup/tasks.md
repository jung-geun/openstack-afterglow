## § 41 — PR 2A: Nodegroup 추상화 레이어 (2026-05-18)

### 41.1 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/migrations/010_k3s_nodegroups.sql` (신규) | `k3s_nodegroups` + `k3s_nodegroup_vms` DDL, 기존 클러스터 SQL 백필 |
| `backend/app/models/db.py` | `K3sNodegroup`, `K3sNodegroupVM` ORM 추가, `K3sCluster.nodegroups` 관계 |
| `backend/app/models/k3s.py` | `K3sNodegroupInfo`, `CreateK3sNodegroupRequest`, `UpdateK3sNodegroupRequest` 추가 |
| `backend/app/services/k3s_nodegroup.py` (신규) | CRUD 서비스 (list/get/create/update/delete + VM 추적 헬퍼) |
| `backend/app/api/k3s/nodegroups.py` (신규) | GET list, GET 단건, POST, PATCH, DELETE 라우터 |
| `backend/app/api/k3s/__init__.py` | `k3s_nodegroups_router` export 추가 |
| `backend/app/main.py` | nodegroups 라우터 `service_k3s_enabled` 가드 하위 등록 |
| `backend/tests/test_k3s_nodegroups.py` (신규) | 16개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `K3sNodegroup`, `K3sNodegroupVM` 인터페이스 추가 |
| `frontend/src/lib/components/dashboard/drover/K3sNodegroupCard.svelte` (신규) | 노드그룹 카드 컴포넌트 |
| `frontend/src/lib/components/dashboard/drover/K3sNodegroupCreateModal.svelte` (신규) | 노드그룹 생성 모달 |
| `frontend/src/lib/components/k3s/K3sNodegroupsSection.svelte` (신규) | 클러스터 상세 내 노드그룹 목록 + 생성/삭제 |
| `frontend/src/lib/components/K3sClusterDetailPanel.svelte` | `K3sNodegroupsSection` 임포트 및 배치 추가 |

### 41.2 검증

- [x] 백엔드 16개 테스트 통과 (`test_k3s_nodegroups.py`)
- [x] svelte-check — 신규 파일 ERROR 없음
- [ ] 실 환경: 기존 클러스터에 백필 SQL 실행 후 `GET /api/k3s/clusters/{id}/nodegroups` 응답 확인
- [ ] 실 환경: 노드그룹 생성 → 수정(node_count) → 삭제 흐름 확인
- [ ] 실 환경: default-server/default-agent 삭제 시 422 응답 확인
- [ ] 클러스터 상세 패널에 노드그룹 섹션 표시 확인

---

