## § 43 — PR 3-A: k3s 인증서 만료 조회 + CA 다운로드 (2026-05-18)

### 43.1 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/app/services/k3s_certs.py` (신규) | `extract_ca_pem`, `parse_kubeconfig_certs`, `probe_tls_server_cert` |
| `backend/app/api/k3s/certificates.py` (신규) | `GET /{id}/ca-certificate`, `GET /{id}/certificate-expiry` |
| `backend/app/api/k3s/__init__.py` | `k3s_certificates_router` 등록 |
| `backend/app/main.py` | `k3s_certificates_router` import + `include_router` (service_k3s_enabled 가드) |
| `backend/app/models/k3s.py` | `CertificateInfo`, `CertificateExpiryResponse` Pydantic 모델 추가 |
| `backend/app/api/identity/admin.py` | 관리자 미러 2개: `GET /k3s-clusters/{id}/ca-certificate`, `GET /k3s-clusters/{id}/certificate-expiry` |
| `backend/tests/test_k3s_certs.py` (신규) | 13개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `CertificateInfo`, `CertificateExpiryResponse` 타입 추가 |
| `frontend/src/lib/components/k3s/K3sClusterInfoCard.svelte` | 인증서 행 (CA 다운로드 버튼 + 만료 조회 버튼) 추가 |
| `frontend/src/lib/components/k3s/K3sCertificateExpiryModal.svelte` (신규) | CA/클라이언트/서버TLS 만료 정보 모달 (days_remaining 색상 chip) |

### 43.2 검증

- [x] 백엔드 13개 테스트 통과 (`test_k3s_certs.py`)
- [x] ruff lint 클린
- [ ] 실 환경: `GET /api/k3s/clusters/{id}/ca-certificate` → PEM 다운로드 확인
- [ ] 실 환경: `GET /api/k3s/clusters/{id}/certificate-expiry` → days_remaining 정상 반환 확인
- [ ] 실 환경: TLS 프로브 가능한 클러스터에서 server_via_tls 배열 확인

---

