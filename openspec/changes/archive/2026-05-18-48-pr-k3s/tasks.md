## § 44 — PR 3-B: k3s 인증서 회전 자동화 (2026-05-18)

k3s 인증서 rolling 회전 — K8s Job(hostPID + nsenter)으로 SSH 없이 `systemctl restart k3s` 트리거.
k3s는 재시작 시 만료 90일 이내 인증서를 자동 갱신한다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/migrations/012_k3s_cert_rotation.sql` (신규) | `last_rotation_at`, `last_rotation_initiated_by` ALTER |
| `backend/app/models/db.py` | `K3sCluster.last_rotation_at`, `last_rotation_initiated_by` 컬럼 추가 |
| `backend/app/models/k3s.py` | `K3sProgressStep.ROTATE_DISCOVER/SERVER/AGENT/VERIFY` 추가 |
| `backend/app/config.py` | `k3s_cert_rotation_node_timeout_sec`, `k3s_cert_rotation_job_image` |
| `generate_k8s.py` | k3s_keys_str/int에 cert rotation 키 추가 |
| `config.toml.example` | [k3s] cert rotation 섹션 문서화 |
| `backend/app/services/k3s_kube.py` | `list_server_nodes`, `create_job`, `wait_job_completed`, `wait_node_ready` |
| `backend/app/services/k3s_db.py` | `record_rotation()` |
| `backend/app/services/k3s_cert_rotation.py` (신규) | `rotate_certificates()` 제너레이터, Redis 락, 캐시 무효화 |
| `backend/app/api/k3s/certificates.py` | `POST /{id}/rotate-certs` SSE 엔드포인트 추가 |
| `backend/app/api/identity/admin.py` | 관리자 미러: `POST /k3s-clusters/{id}/rotate-certs` |
| `frontend/src/lib/components/k3s/K3sCertificateExpiryModal.svelte` | "인증서 회전" 버튼 (HA 전용) |
| `frontend/src/lib/components/k3s/K3sRotateProgressModal.svelte` (신규) | SSE 스트림 진행률 모달 |
| `backend/tests/test_k3s_cert_rotation.py` (신규) | 12개 테스트 |

### 완료 기준

- [x] 백엔드 12개 테스트 통과 (`test_k3s_cert_rotation.py`)
- [x] PR 3-A 회귀 없음 (`test_k3s_certs.py` 13개 통과)
- [x] ruff lint 클린
- [ ] 실 환경: HA(3-master) 클러스터에서 회전 → SSE 스트림 완료, cert NotAfter 갱신 확인
- [ ] 실 환경: 단일 마스터 클러스터에서 회전 → 422 확인
- [ ] 실 환경: 동시 회전 → 두 번째 요청 409 확인

---

