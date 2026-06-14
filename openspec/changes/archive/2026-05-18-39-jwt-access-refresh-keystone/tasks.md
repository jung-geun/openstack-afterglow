## 35. JWT access+refresh 토큰 도입 — Keystone 토큰 백엔드 격리 (2026-05-18)

### 35.1 동기

- Keystone 1시간 토큰을 localStorage에 평문 저장 → 보안 취약 + 자주 재로그인 필요
- Afterglow 자체 JWT 발급(access 15분 + refresh 7일): frontend는 JWT만 보유, Keystone 토큰은 backend Redis에 격리

### 35.2 신규 파일

- [x] `backend/app/services/jwt_service.py` — HS256 access/refresh 서명·검증 (`sign_access`, `verify_access`, `sign_refresh`, `verify_refresh`)
- [x] `backend/app/services/session_store.py` — `afterglow:refresh:{jti}` Redis 키로 Keystone 토큰 매핑 (TTL=refresh 만료까지)
- [x] `backend/tests/test_auth_jwt.py` — 14개 테스트: JWT 서명·검증, 세션 저장소, 로그인 응답, Bearer 인증, 레거시 X-Auth-Token, 만료 JWT 401, 토큰 회전(replay 방지), 로그아웃 후 refresh 401

### 35.3 백엔드 수정

- [x] `backend/app/api/identity/auth.py` — `/login`, `/gitlab/callback` 응답에 `token`(access JWT) + `refresh_token` 쌍 발급, `/refresh` 엔드포인트(토큰 회전), `/switch-project` 엔드포인트 추가
- [x] `backend/app/api/deps.py` — `Authorization: Bearer` 우선 처리 (`_resolve_jwt_token_info`), 레거시 `X-Auth-Token` fallback 유지 (dual-path)
- [x] `backend/app/models/auth.py` — `TokenResponse`에 `refresh_token: str | None` 추가
- [x] `backend/app/config.py` + `config.toml.example` + `generate_k8s.py` — `jwt_access_ttl=900`, `jwt_refresh_ttl=604800` 동기화
- [x] `backend/pyproject.toml` — `pyjwt>=2.9.0` 의존성 추가

### 35.4 프론트엔드 수정

- [x] `frontend/src/lib/stores/auth.ts` — `refreshToken`, `accessExpiresAt` 필드 추가, `getAccessSecondsRemaining()` 헬퍼
- [x] `frontend/src/lib/api/client.ts` — `Authorization: Bearer` 헤더 전환, 401 시 `tryRefresh()` + 1회 재시도, `_refreshPromise` coalescing으로 동시 refresh 직렬화
- [x] `frontend/src/routes/+layout.svelte` — session-info 폴링 제거, JWT exp 기반 60초 타이머 auto-refresh (만료 2분 전)
- [x] `frontend/src/routes/+page.svelte`, `auth/gitlab/callback/+page.svelte` — `accessExpiresAt` 저장, `refreshToken` 저장
- [x] 직접 fetch 헤더 Bearer 전환: `k3sSseStream.ts`, `vmCreateStore.svelte.ts`, `k3sClusterDetail.svelte.ts`, `objectBrowser.svelte.ts`, `admin/notion/+page.svelte`, `dashboard/drover/+page.svelte`

### 35.5 검증

- [x] 149개 백엔드 테스트 통과 (14개 신규 JWT 테스트 포함)
- [x] `npm run check` — PR 2 관련 신규 에러 없음
- [ ] 실 환경: 로그인 → 16분 후 access 자동 갱신 → API 정상 동작, 로그아웃 후 refresh 재사용 차단


---

