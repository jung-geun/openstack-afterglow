## 37. Keystone System Scope(`system:all`) 도입 — 자기복제 권한 상승 차단 (2026-05-18)

### 37.1 동기

기존 admin 판별 정책("admin project + admin role")의 구조적 약점: 현 admin이
`/api/admin/roles/assign`으로 다른 사용자에게 `admin role on admin project`를 부여하면,
그 사용자도 자동으로 system admin이 된다(`require_admin` 만으로 막을 수 없음). 이를
Keystone system-scoped role (`scope.system=all`)로 대체하여 project-scope `assign_role`
호출로는 system admin이 만들어지지 않도록 차단. 호환 모드(`admin_legacy_project_policy=true`)로
한 릴리스 동안 기존 admin을 OR 인정하여 무중단 마이그레이션 지원.

### 37.2 변경 파일

- [x] `backend/app/config.py` — `_load_toml()` `[security]` 섹션 매핑 + `Settings.admin_legacy_project_policy: bool = True`
- [x] `generate_k8s.py` — `_render_toml_for_k8s()` 에 `[security]` 블록 추가 (configmap 인라인)
- [x] `backend/app/services/keystone.py` — `_is_system_admin` dual-mode 재작성:
  - `_has_system_admin_role(user_id)`: `role_assignments.list(system="all")` 검사
  - `_has_admin_project_role(user_id)`: 기존 project-scope 검사 (호환 모드용)
  - `_is_system_admin`: `_has_system_admin_role OR (admin_legacy_project_policy AND _has_admin_project_role)`
  - `invalidate_admin_caches()`: 캐시 리셋 헬퍼
- [x] `backend/app/api/identity/admin_identity.py` — System Roles 섹션 신규 엔드포인트 3개:
  - `GET /api/admin/identity/system-roles` — system:all admin 보유자 목록
  - `POST /api/admin/identity/system-roles/grant` — system role 부여 + 세션 즉시 무효화 + audit
  - `POST /api/admin/identity/system-roles/revoke` — system role 회수 + 세션 즉시 무효화 + audit

### 37.3 테스트

- [x] `backend/tests/test_keystone_system_scope.py` (신규, 4개):
  - `test_system_role_grants_admin_regardless_of_compat`: system role 보유 → 호환 모드 무관 True
  - `test_admin_project_role_with_compat_on`: project role + 호환 ON → True
  - `test_admin_project_role_with_compat_off`: project role + 호환 OFF → False
  - `test_no_role_returns_false`: 권한 없음 → False
- [x] `backend/tests/test_admin_identity.py` 확장 (3개):
  - `test_list_system_roles_requires_admin`: non_admin → 403
  - `test_grant_system_role_revokes_sessions`: grant → `revoke_user_sessions` + `admin_system_role_grant` audit
  - `test_revoke_system_role_revokes_sessions`: revoke → `revoke_user_sessions` + `admin_system_role_revoke` audit

### 37.4 마이그레이션 절차

1. **PR B 배포** (`admin_legacy_project_policy=true`, 호환 모드 ON) — 기존 admin 사용자 즉시 영향 없음.
2. 운영 admin 1명에게 system role 수동 부여:
   ```bash
   openstack role add --system all --user <user-id> admin
   ```
   Afterglow `/admin` 정상 동작 확인.
3. 기존 admin project 멤버 전원에게 system role 부여 — `POST /api/admin/identity/system-roles/grant` 일괄 호출.
4. **다음 릴리스**: `config.toml`에서 `[security] admin_legacy_project_policy = false` 전환.
5. **다다음 릴리스**: 호환 분기 코드 + `admin_legacy_project_policy` 설정 키 + `_has_admin_project_role` 헬퍼 제거.

**policy.yaml 권장 변경** (운영자 별도 적용):
```yaml
"identity:list_users": "role:admin and system_scope:all"
"identity:create_role_assignment_on_system": "role:admin and system_scope:all"
```

### 37.5 검증

- [x] 58개 백엔드 테스트 통과 (`test_keystone_system_scope.py` + `test_admin_identity.py` + `test_auth_jwt.py`)
- [x] `ruff check` + `ruff format` — 수정 파일 lint/format 통과
- [ ] 실 환경: system role 부여(CLI) → admin 라우트 정상, admin project 멤버십 제거 후에도 admin 유지
- [ ] 실 환경: system role 박탈 → 즉시 강제 로그아웃 + 다음 API 401
- [ ] 실 환경: 호환 모드 OFF에서 project-scope admin role 부여 → `/admin` 403 (자기복제 차단 확인)

---

