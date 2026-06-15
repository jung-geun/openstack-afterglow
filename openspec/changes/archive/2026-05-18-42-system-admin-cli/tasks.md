## § 38 — System Admin 계정 관리 (CLI + 관리자 페이지)

**동기**: PR B(`e05d8c9`)로 system:all scope 판별과 grant/revoke 엔드포인트가 생겼지만, 운영자가 활용하려면 ① 첫 admin 부트스트랩 수단, ② 일상 관리 UI, ③ 마지막 admin lockout 방지가 필요하다.

### 38.1 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/app/api/identity/admin_identity.py` | `list_system_roles` 응답 enrich (`name/email/enabled`); `revoke_system_role` lockout 가드 (count≤1 → 422) |
| `backend/tests/test_admin_identity.py` | 3개 테스트 추가 (enrich 검증, 마지막 admin 422, 2명 시 200) |
| `scripts/manage_system_admins.py` (신규) | argparse CLI — `list/grant/revoke`, `--os-system-scope` 옵션 |
| `frontend/src/routes/admin/system-admins/+page.svelte` (신규) | 시스템 관리자 관리 페이지 |
| `frontend/src/lib/components/admin/system-admins/SystemAdminTable.svelte` (신규) | 목록 테이블 + 회수 버튼 (마지막 1명 disabled, self-revoke confirm) |
| `frontend/src/lib/components/admin/system-admins/SystemAdminGrantModal.svelte` (신규) | 사용자 검색 모달 → grant 호출 |
| `frontend/src/lib/components/AdminSidebar.svelte` | Identity 섹션에 '시스템 관리자' 메뉴 추가 |

### 38.2 CLI 사용법

```bash
# 환경 설정
export OS_AUTH_URL=https://keystone.example.com/v3
export OS_USERNAME=admin OS_PASSWORD=...
export OS_PROJECT_NAME=admin OS_USER_DOMAIN_NAME=Default

# 현재 system admin 목록
python3 scripts/manage_system_admins.py list

# 부여 (user_id 또는 name)
python3 scripts/manage_system_admins.py grant alice@example.com

# 회수 (lockout 가드 없음 — 부트스트랩/복구 수단)
python3 scripts/manage_system_admins.py revoke alice@example.com

# Keystone secure-RBAC 환경 첫 grant 부트스트랩
python3 scripts/manage_system_admins.py --os-system-scope grant <user-id>
```

### 38.3 검증

- [x] 43개 백엔드 테스트 통과 (`test_admin_identity.py` + `test_keystone_system_scope.py`)
- [x] `ruff format` — 수정 파일 포맷 통과
- [x] frontend 신규 파일 — svelte-check 에러 없음
- [ ] 실 환경: CLI `list` → 빈 목록 정상
- [ ] 실 환경: CLI `grant` → `GET /api/admin/identity/system-roles` 응답에 name/email 포함 확인
- [ ] 실 환경: UI `/admin/system-admins` — 1명 표시 시 회수 버튼 disabled
- [ ] 실 환경: UI grant 후 2명 → 첫 admin self-revoke → 즉시 로그아웃
- [ ] 실 환경: 1명 남은 상태에서 `curl POST .../revoke` → 422

---

