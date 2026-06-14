## 64. Barbican Key Manager 대시보드 (2026-06-01)

> **목표**: OpenStack Barbican을 통해 사용자가 비밀번호·인증서·암호화 키를 안전하게 저장·관리하고, 관리자가 프로젝트별 쿼터를 제어하는 Key Manager 대시보드 구현.
> 인증서 **저장**만 지원 (CA 발급/certificate order는 OpenStack deprecated — 구현 제외).

### 64.1 백엔드 서비스 래퍼 확장

- [x] `backend/app/services/barbican.py` — KEK 헬퍼 유지 + 범용 Key Manager 함수 추가
  - [x] `SYSTEM_MANAGED_PREFIXES`, `_is_system_managed()` — `afterglow-` prefix secret 보호
  - [x] `list_secrets`, `get_secret_meta`, `get_secret_payload`, `create_secret`, `delete_secret` (시스템 관리 secret 삭제 차단)
  - [x] `list_containers`, `create_container`, `delete_container`
  - [x] `list_orders`, `create_order`, `get_order`, `delete_order`
  - [x] `get_acl`, `set_acl`, `delete_acl` (raw REST)
  - [x] `list_secret_consumers`, `list_container_consumers` (raw REST)
  - [x] `get_effective_quota`, `list_project_quotas`, `get_project_quota`, `set_project_quota`, `delete_project_quota` (raw REST)

### 64.2 Pydantic 모델

- [x] `backend/app/models/barbican.py` — `SecretInfo`, `SecretCreateRequest`, `ContainerInfo`, `ContainerCreateRequest`, `OrderInfo`, `OrderCreateRequest`, `AclSetRequest`, `QuotaInfo`, `ProjectQuotaSetRequest`

### 64.3 사용자 라우터 (`backend/app/api/secrets/`)

- [x] `secrets.py` — GET/POST/DELETE secret, GET payload (캐시 제외), GET/PUT/DELETE ACL, GET consumers, GET quota/effective
- [x] `containers.py` — GET/POST/DELETE container, GET/PUT ACL, GET consumers
- [x] `orders.py` — GET/POST/GET/{id}/DELETE order
- [x] `main.py` — `service_barbican_enabled` 가드 아래 4개 라우터 조건부 마운트

### 64.4 관리자 라우터

- [x] `backend/app/api/identity/admin_secrets.py` — 프로젝트 쿼터 CRUD (`require_admin` 필수), `/api/admin/key-manager/project-quotas`

### 64.5 테스트

- [x] `backend/tests/test_secrets.py` — 401/성공/시스템 secret 삭제 차단/payload 비캐시 검증 (6개)
- [x] `backend/tests/test_secrets_admin.py` — 관리자 전용 쿼터 CRUD 403/성공 검증 (7개)

### 64.6 프론트엔드

- [x] `frontend/src/lib/api/secrets.ts` — `secretsApi` 클라이언트 (secrets/containers/orders/quota/admin 전 엔드포인트)
- [x] `frontend/src/routes/dashboard/secrets/+page.svelte` — 4탭(비밀/컨테이너/Key Orders/쿼터), payload 1회 조회·복사·가림, 시스템 관리 secret 잠금
- [x] `frontend/src/routes/admin/secrets/+page.svelte` — 프로젝트별 쿼터 설정/초기화 관리
- [x] `Sidebar.svelte` — Key Manager 섹션 추가 (`/dashboard/secrets`)
- [x] `AdminSidebar.svelte` — Key Manager 항목 추가 (`/admin/secrets`)
- [ ] 프로비저닝 내구성: stale in-flight reconcile 루프

