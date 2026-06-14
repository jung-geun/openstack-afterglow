## 63. Stampede 모드 — drover(k3s) 노드 오토스케일 (2026-06-01)

### 63.1 목표

사용자가 pod만 배포하면 drover 내부 reconcile 루프가 자동으로 노드(VM)를 확장/축소한다 (GCP Autopilot 유사). 노드그룹 단위로 스케일하며, flavor는 pending pod requests + 기존 부하 가중치로 자동 선택.

### 63.2 Backend

- [x] `backend/migrations/014_stampede.sql` — `k3s_clusters.stampede_enabled`, `k3s_nodegroups.{stampede_enabled, min_size, max_size, stampede_state}` DDL
- [x] `backend/app/models/db.py` — `K3sCluster.stampede_enabled`, `K3sNodegroup.{stampede_enabled, min_size, max_size, stampede_state}` ORM 컬럼 추가
- [x] `backend/app/services/k3s_db.py` — `_cluster_to_dict`에 `stampede_enabled` 필드 추가
- [x] `backend/app/services/k3s_nodegroup.py` — `_ng_to_dict`에 Stampede 필드 추가, `update_nodegroup` 허용 컬럼 set 갱신
- [x] `backend/app/services/k3s_kube.py` — Stampede 전용 5개 함수 신규: `list_unschedulable_pods`, `get_node_capacity`, `get_pod_resource_usage`, `cordon_node`, `drain_node` + K8s 수량 파서(`_parse_cpu_millicores`, `_parse_memory_bytes`)
- [x] `backend/app/services/k3s_autoscale.py` (신규) — `provision_nodegroup_vms`, `delete_nodegroup_vms`: `_scale_agents` 로직을 노드그룹 파라미터(flavor/labels/taints)로 일반화 추출
- [x] `backend/app/services/k3s_stampede.py` (신규) — Stampede Reconciler: fit-check(PVC/affinity/taint 필터), 가중치 기반 flavor 선택(`_select_flavor`), scale-up(in-flight 추적, max 가드레일), scale-down(stabilization window, min 가드레일, cooldown), `run_all()`
- [x] `backend/app/worker.py` — `init_db()` 호출 추가, `_stampede_loop()` 추가(기본 60초 주기)
- [x] `backend/app/api/k3s/clusters.py` — Stampede API 3개: `POST .../stampede/enable`, `POST .../stampede/disable`, `GET .../stampede`
- [x] `backend/app/config.py` — Stampede 설정 8개 필드: `k3s_stampede_{enabled, interval, scale_down_threshold, scale_down_window, scale_up_cooldown, scale_down_cooldown, resource_headroom_factor, project_id}`
- [x] `config.toml.example` — Stampede 설정 섹션 문서화
- [x] `generate_k8s.py` — Stampede 설정 8개 k3s configmap 항목 추가
- [x] `backend/tests/test_k3s_stampede.py` (신규) — 23개 단위 테스트 전통과: fit-check, flavor 선택, CPU/메모리 파서, API 엔드포인트 계약, scale-up max 가드레일, scale-down min 가드레일

### 63.3 Frontend (미구현 — 후속)

- [x] `K3sNodegroupCard.svelte` / `K3sNodegroupCreateModal.svelte` — min/max/stampede 토글 UI
- [x] `K3sClusterDetailPanel.svelte` / `K3sClusterInfoCard.svelte` — Stampede 상태 뱃지
- [x] `K3sClusterMainPanel.svelte` — `enableStampede` / `disableStampede` 액션 (클러스터 ACTIVE 시 활성화 버튼 표시)

### 63.4 Phase 2 (후속)

- [ ] OpenStack 프로젝트 격리 (`stampede_project_id`): Stampede VM/LB를 서비스 프로젝트에 생성
- [ ] scale-from-zero (min=0): 노드 0개 상태에서 cold-start 프로비저닝
- [ ] 멀티 nodegroup 동시 오토스케일
- [ ] 스케일 이벤트 이력 조회 API/UI

---

