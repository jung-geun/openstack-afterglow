## 69. 보안 취약점 감사 및 강화

3-도메인 병렬 감사(인증/세션·인젝션/명령실행·암호화/인가/웹) 결과 발견된 취약점 전수 수정.

### 69.1 CRITICAL/HIGH 수정

- [x] **B1 — k3s nodegroup labels/taints 명령 주입 차단** (CRITICAL): `models/k3s.py` K8s 문자 문법 Pydantic validator, root cloud-init RCE 방어
- [x] **A2 — k3s 템플릿/빌더 shlex_quote 적용** (CRITICAL 방어심층): `k3s_agent.yaml.j2`, `k3s_server.yaml.j2`, `k3s_cloudinit.py` FCOS f-string 전 변수 `| shlex_quote` 통일
- [x] **B2 — JWT 경로 idle/absolute 세션 타임아웃 적용** (HIGH): `deps.py` `_resolve_jwt_token_info` + `/refresh` 엔드포인트에 `_check_session_timeout` 연결
- [x] **B4 — GitLab OIDC nonce 검증 추가** (HIGH): `gitlab_oidc.py` nonce 생성/Redis 저장/콜백 검증으로 id_token 재생 공격 차단
- [x] **C4 — X-Auth-Token 레거시 경로 제거 + Bearer 마이그레이션** (HIGH): `deps.py` X-Auth-Token 분기 제거, 모든 엔드포인트 Bearer JWT 단일화
- [x] **C1 — 계정 잠금 서브시스템** (CRITICAL): `services/login_guard.py` Redis 기반 실패 카운트·지수 백오프·일시 잠금, 관리자 해제 엔드포인트

### 69.2 MEDIUM 수정

- [x] **A1 — SD 토큰 타이밍 공격 방어**: `sd_targets.py` `hmac.compare_digest` 교체
- [x] **B3 — delete_session_owned 소유권 이중 검증**: `session_store.py` Redis 인덱스 + 세션 데이터 user_id 재확인
- [x] **C5 — token-binding fail-closed**: `deps.py` 바인딩 오류 시 401, `token_binding.py` 알 수 없는 mode → ValueError

### 69.3 LOW 수정

- [x] **A3 — 초대 이메일 HTML 인젝션 방어**: `email_service.py` `html.escape()` 적용
- [x] **A4 — Trove DEBUG 로그 비밀번호 redact**: `trove.py` users[].password → `"***"`

### 69.4 정책/아키텍처 변경

- [x] **C2 — admin_legacy_project_policy 기본값 False**: `config.py` system:all 스코프만 시스템 관리자 인정 (자기복제 권한 상승 차단)
- [x] **C3 — bootstrap_system_admin.py**: `backend/scripts/` lockout 복구·마이그레이션용 CLI (API 우회, Keystone 직접 접속)
- [x] **config.py — token_ip_binding_mode 시작 시 검증**: 유효하지 않은 모드 설정 시 부팅 거부

### 69.5 설정 동기화

- [x] `config.py`, `generate_k8s.py`, `config.toml.example` — `login_max_attempts`, `login_lockout_seconds`, `login_backoff_base` 동기화
- [x] `config.toml.example` — `admin_legacy_project_policy = false` 마이그레이션 안내 주석

### 69.6 구현 파일

- [x] `backend/app/services/login_guard.py` (신규)
- [x] `backend/scripts/bootstrap_system_admin.py` (신규)
- [x] `backend/app/models/k3s.py` — labels/taints validator
- [x] `backend/app/api/deps.py` — JWT 타임아웃·fail-closed·X-Auth-Token 제거
- [x] `backend/app/api/identity/auth.py` — login_guard 통합, refresh 타임아웃
- [x] `backend/app/services/gitlab_oidc.py` — nonce 검증
- [x] `backend/app/services/session_store.py` — 소유권 이중 검증
- [x] `backend/app/services/token_binding.py` — 알 수 없는 mode fail-closed
- [x] `backend/app/api/common/sd_targets.py` — hmac.compare_digest
- [x] `backend/app/services/email_service.py` — html.escape
- [x] `backend/app/services/trove.py` — log redact
- [x] `backend/app/api/identity/admin_identity.py` — unlock 엔드포인트, X-Auth-Token 제거
- [x] `backend/app/api/union/layers.py` — X-Auth-Token 제거
- [x] `backend/app/api/object_storage/containers.py` — X-Auth-Token 제거
- [x] `backend/app/main.py` — CORS X-Auth-Token 제거
- [x] `frontend/src/lib/components/k3s/K3sRotateProgressModal.svelte` — Bearer 마이그레이션
- [x] `backend/app/templates/k3s_agent.yaml.j2`, `k3s_server.yaml.j2` — shlex_quote
- [x] `backend/app/services/k3s_cloudinit.py` — shlex.quote FCOS

### 69.7 테스트

- [x] `backend/tests/test_security_mechanical.py` — A1/A3/A4 단위 테스트
- [x] `backend/tests/test_k3s_nodegroup_security.py` — B1 labels/taints 거부 (18건)
- [x] `backend/tests/test_session_security.py` — B3/B4 세션 소유권·OIDC nonce (9건)
- [x] `backend/tests/test_jwt_session_timeout.py` — B2 JWT 타임아웃 적용 (5건)
- [x] `backend/tests/test_login_guard.py` — C1 잠금 임계값·백오프·해제 (9건)
- [x] `backend/tests/test_x_auth_token_removal.py` — C4 X-Auth-Token 거부 (6건)

---

