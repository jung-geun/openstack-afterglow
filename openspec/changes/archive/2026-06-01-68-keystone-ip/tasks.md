## 67. 토큰 보안: 전체 로그아웃 · Keystone 직접 폐기 · IP/지문 바인딩 블랙리스트

### 67.1 목표

- [x] 관리자가 특정 사용자의 전체 토큰을 Keystone까지 직접 폐기 (요구사항 A)
- [x] 사용자 셀프서비스 "모든 위치에서 로그아웃" — Keystone 직접 폐기 포함 (요구사항 B)
- [x] 관리자 페이지 강제 전체 로그아웃 (요구사항 B)
- [x] 토큰 최초 생성 IP + 기기 지문(User-Agent 해시) 기록 및 회전 너머 운반
- [x] 마지막 사용 IP/지문 갱신 (쓰로틀 60s)
- [x] IP/지문 불일치 시 자동 차단 + 블랙리스트 등록 (요구사항 C)
- [x] `token_ip_binding_mode` 설정 토글 (off/log/subnet/strict)

### 67.2 구현 파일

- [x] `backend/app/services/session_store.py` — `store_session` origin 파라미터, `revoke_user_sessions` Keystone 폐기, `blacklist_session`, `touch_session_seen`, `list_user_sessions` 추가
- [x] `backend/app/services/token_binding.py` — 신규: `get_origin`, `check_binding`, `_same_subnet`
- [x] `backend/app/api/deps.py` — `_resolve_jwt_token_info`에 블랙리스트·바인딩 검사 추가
- [x] `backend/app/api/identity/auth.py` — origin 발급·운반, `POST /logout-all`, `GET /sessions`
- [x] `backend/app/api/identity/admin_identity.py` — `POST /users/{id}/revoke-sessions`, `GET /users/{id}/sessions`
- [x] `backend/app/config.py` — `token_ip_binding_mode` 설정 추가
- [x] `generate_k8s.py`, `config.toml.example` — 설정 동기화
- [x] `frontend/src/lib/components/account/SecuritySection.svelte` — 신규 세션 보안 카드
- [x] `frontend/src/routes/dashboard/account/+page.svelte` — SecuritySection 추가
- [x] `frontend/src/lib/components/admin/users/AdminUserEditModal.svelte` — 강제 세션 폐기 버튼 추가

### 67.3 설계 결정

- **MAC 주소 대체**: 웹에서 수집 불가 → User-Agent·Accept-Language·Accept-Encoding 해시(기기 지문)로 대체
- **불일치 기본 정책**: /24(IPv4)·/64(IPv6) 서브넷 일치 허용 (모바일/NAT false-positive 방지)
- **origin 재핀 금지**: refresh 회전 시 최초 로그인 origin 그대로 운반
- **Keystone 폐기**: `revoke_user_sessions`에서 best-effort 직접 폐기 (실패해도 Redis 세션 삭제 진행)
- **레거시 세션 백필**: origin 미기록 세션은 즉시 통과 (배포 시 대량 로그아웃 방지)

### 67.4 테스트

- [x] `backend/tests/test_token_binding.py` — 순수 함수 + 세션 헬퍼 + 엔드포인트 통합 테스트

