## § 42 — PR 2B: k3s 마스터 HA (embedded etcd, LB-first) (2026-05-18)

### 42.1 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/migrations/011_k3s_master_ha.sql` (신규) | `k3s_clusters.master_count INT NOT NULL DEFAULT 1` ALTER |
| `backend/app/models/db.py` | `K3sCluster.master_count` 컬럼 추가 |
| `backend/app/models/k3s.py` | `K3sProgressStep` HA 단계 추가, `CreateK3sClusterRequest.master_count` (1\|3 validator), `K3sClusterInfo.master_count` |
| `backend/app/services/k3s_cluster.py` | `create_ha_callback_token`, `consume_ha_callback_token`, `get_ha_join_count`, `incr_ha_join_count` 추가 |
| `backend/app/services/k3s_db.py` | `_cluster_to_dict`, `create_cluster_record`, `_column_map`에 `master_count` 추가, HA 토큰/카운터 래퍼 추가 |
| `backend/app/services/k3s_cloudinit.py` | `generate_server_userdata` + `_build_server_ignition`에 `cluster_init`, `join_url`, `ha_node_token` 파라미터 추가 |
| `backend/app/templates/k3s_server.yaml.j2` | `cluster_init`/`join_url` HA 분기 추가 |
| `backend/app/services/k3s_provisioner.py` (신규) | `provision_agents` (callback.py에서 이전) + `bootstrap_ha_servers` |
| `backend/app/api/k3s/clusters.py` | Step 1-B HA LB+FIP 생성, `cluster_init` 전달, HA 필드 저장, `_rollback` lb_id/fip_id, `_cluster_to_info` master_count |
| `backend/app/api/k3s/callback.py` | HA/일반 토큰 이중 시도, server_index 분기, `_handle_ha_joiner`, provision_agents → k3s_provisioner 이전 |
| `backend/app/config.py` | `k3s_api_lb_floating_network_id` 추가 (Settings + _load_toml) |
| `backend/tests/test_k3s_master_ha.py` (신규) | 11개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `K3sCluster.master_count?: number` 추가 |
| `frontend/src/lib/components/dashboard/drover/K3sCreateClusterModal.svelte` | `master_count` 폼 필드, 1/3 토글 UI 추가 |

### 42.2 검증

- [x] 백엔드 11개 테스트 통과 (`test_k3s_master_ha.py`)
- [ ] 실 환경: master_count=3 클러스터 생성 → LB+FIP 자동 생성, server#2/3 join 확인
- [ ] 실 환경: server#1 강제 종료 → kubectl 페일오버 5초 내 확인
- [ ] 실 환경: master_count=2 요청 → 422 응답 확인

---

