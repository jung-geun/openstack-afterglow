## 36. JWT stale 제거 + admin role 변동 즉시 반영 + audit (2026-05-18)

### 36.1 동기

PR 35(JWT 도입) 이후 access JWT(TTL 15분) payload에 `is_system_admin`/`roles`가 박혀 **admin role 박탈 후 15분간 admin으로 인식**되는 stale 윈도우 발생. X-Auth-Token 경로의 60s 캐시보다 후퇴한 보안 수준.

### 36.2 변경 파일

- [x] `backend/app/services/jwt_service.py` — `sign_access()`에서 `roles`/`is_system_admin` 파라미터 및 payload 클레임 제거. JWT는 신원 정보(sub, username, project_id, project_name, jti, rjti)만 보유.
- [x] `backend/app/api/identity/auth.py` — `_build_token_response()`의 `sign_access()` 호출에서 해당 인자 제거. `TokenResponse` 응답에는 초기 렌더링용으로 계속 포함.
- [x] `backend/app/api/deps.py` — `_resolve_jwt_token_info()` 정상 경로(프로젝트 전환 없음)도 `_cached_validate()` 호출로 통합. JWT payload의 stale 권한 사용 제거. stale window: 15분 → 60초(캐시 TTL).
- [x] `backend/app/services/session_store.py` — 보조 인덱스 `afterglow:user-sessions:{user_id}` SET 도입. `store_session`에 SADD, `delete_session`에 SREM 연동. `revoke_user_sessions(user_id)` 신규: 사용자 전체 세션 즉시 삭제.
- [x] `backend/app/api/identity/admin_identity.py` — `assign_role`/`revoke_role`에 `Depends(get_token_info)` 추가. `_resolve_admin_ids()`로 admin_role_id 비교 후 분기: admin role 변동 → `revoke_user_sessions` + audit; 일반 role 변동 → audit만.
- [x] `frontend/src/lib/api/client.ts` — `/api/admin/` 경로 403 응답 시 `handleAdminForbidden()`: `isSystemAdmin=false` 강등 + `/dashboard` 이동. one-shot 가드로 무한 루프 방지.
- [x] `frontend/src/routes/admin/+layout.svelte` — `onMount` 시 `/me` 강제 호출하여 stale 캐시 우회 + 즉시 권한 동기화.

### 36.3 테스트

- [x] `backend/tests/test_auth_jwt.py` 확장 (51개 통과):
  - `test_access_payload_no_auth_claims`: JWT payload에 `roles`/`is_system_admin` 없음 검증
  - `test_revoke_user_sessions`: 사용자 전체 세션 삭제, 다른 유저 세션 불변
  - `test_revoke_user_sessions_empty`: 세션 없는 유저 → 0 반환
  - `test_bearer_jwt_uses_cached_validate_not_payload`: Bearer JWT 경로가 JWT payload 대신 `_cached_validate`로 권한 결정함을 검증
- [x] `backend/tests/test_admin_identity.py` 확장 (51개 통과):
  - `test_assign_admin_role_revokes_sessions`: admin role 할당 → `revoke_user_sessions` 호출 + `admin_role_grant` audit
  - `test_assign_non_admin_role_no_revoke`: 일반 role 할당 → `revoke_user_sessions` 미호출 + `role_grant` audit
  - `test_revoke_admin_role_revokes_sessions`: admin role 회수 → `revoke_user_sessions` 호출 + `admin_role_revoke` audit
  - `test_revoke_non_admin_role_no_revoke`: 일반 role 회수 → `revoke_user_sessions` 미호출 + `role_revoke` audit

### 36.4 검증

- [x] 51개 백엔드 테스트 통과
- [x] `ruff check` — 수정 파일 lint 통과
- [ ] 실 환경: admin role 박탈 후 즉시 강제 로그아웃 확인, /admin 접근 시 403 → /dashboard 이동 확인

