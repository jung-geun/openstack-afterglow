## § 39 — 호환 모드 마이그레이션 완성 (가시화 + 일괄 promote + 안전망)

**동기**: PR B 도입 후 `admin_legacy_project_policy=true` 호환 모드에서 strict 모드(`=false`)로 전환하기 위해 운영자에게 필요한 도구가 부재했다. admin project 멤버 일괄 promote 자동화, 현재 모드 가시화, lockout 안전망을 추가해 마이그레이션 절차 Step 3·4를 실행 가능하게 했다.

### 39.1 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/app/api/identity/admin_identity.py` | `GET /identity/security-policy` (모드+카운트 반환), `POST /identity/system-roles/migrate-from-project` (일괄 grant) 신규 엔드포인트 |
| `backend/app/main.py` startup | compat OFF + system admin 0명이면 `_logger.error()` lockout 경고 |
| `backend/tests/test_admin_identity.py` | 4개 테스트 추가 (security-policy 403/정상, migrate 403/정상) |
| `scripts/manage_system_admins.py` | `migrate-from-project` 서브커맨드 추가 |
| `frontend/src/routes/admin/system-admins/+page.svelte` | security-policy 병렬 fetch + SecurityPolicyBanner + MigrateModal 통합 |
| `frontend/src/lib/components/admin/system-admins/SecurityPolicyBanner.svelte` (신규) | 3-상태 배너 (compat ON/OFF+count>0/OFF+count=0) |
| `frontend/src/lib/components/admin/system-admins/MigrateModal.svelte` (신규) | 일괄 마이그레이션 확인 다이얼로그 + 결과 표시 |

### 39.2 CLI 사용법

```bash
# 호환 모드 → strict 전환 직전 일괄 마이그레이션
python3 scripts/manage_system_admins.py migrate-from-project

# 출력 예시:
# OK: alice (a1b2...) granted (system admin)
# SKIP: bob (b2c3...) already system admin
# 완료: 1명 grant, 1명 skip, 0건 오류
```

### 39.3 검증

- [x] 47개 백엔드 테스트 통과 (`test_admin_identity.py` + `test_keystone_system_scope.py`)
- [x] `ruff check` + `ruff format` — 수정 파일 lint/format 통과
- [x] frontend 신규 파일 — svelte-check ERROR 없음 (a11y WARNING은 기존 패턴과 동일)
- [ ] 실 환경: compat ON 상태에서 UI 노란 배너 + "일괄 마이그레이션" 버튼 확인
- [ ] 실 환경: 마이그레이션 실행 → migrated/skipped 카운트 정확히 반환
- [ ] 실 환경: `admin_legacy_project_policy=false` 후 재시작 → 초록 배너
- [ ] 실 환경: compat OFF + system admin 0명 → startup ERROR 로그 + 빨간 배너

---

