## Phase 56 — 프로젝트 선택 페이지 + 로그인 후 자동 전환 (2026-05-23)

### 56.1 목표

로그인됐지만 프로젝트가 미선택인 상태에서 대시보드를 열면 모든 API가 오류를 내는 문제를 해결.
Google Cloud Console 스타일의 `/select-project` 페이지를 도입하여 사용자가 명시적으로 프로젝트를 고르게 한다.

### 56.2 구현

**백엔드**
- [x] `backend/app/models/auth.py` — `ProjectInfo`에 `domain_name`, `last_accessed_at` 옵션 필드 추가
- [x] `backend/app/services/keystone.py` — `list_projects()` 내 도메인 목록 1회 조회 → `domain_name` 채움
- [x] `backend/app/services/recent_projects.py` (신규) — Redis Sorted Set `afterglow:recent_projects:{user_id}` 기반 최근 접근 기록/조회 헬퍼 (TTL 30일)
- [x] `backend/app/api/identity/auth.py` — `GET /api/auth/projects/recent` 엔드포인트 신설 (Redis 순 정렬 + 미기록 프로젝트 이름순 후미 배치)
- [x] `backend/app/api/identity/auth.py` — login / gitlab_callback / switch-project 에서 `record_project_access` 호출
- [x] `backend/app/api/deps.py` — `_resolve_jwt_token_info` 내 실제 rescope 시 `asyncio.create_task(record_project_access(...))` fire-and-forget

**프론트엔드**
- [x] `frontend/src/lib/stores/auth.ts` — `Project` 인터페이스 `export` + `domain_name`, `last_accessed_at` 옵션 필드 추가
- [x] `frontend/src/routes/+layout.svelte` — `$authReady && $isLoggedIn && !projectId` guard `$effect` 추가 → `/select-project` 리다이렉트; `/select-project` 경로에서 nav/sidebar 제외한 미니멀 레이아웃 분기
- [x] `frontend/src/routes/+page.svelte` — 로그인 후 분기: default_project_id 일치 또는 단일 프로젝트면 `/dashboard`, 그 외 `/select-project`
- [x] `frontend/src/routes/auth/gitlab/callback/+page.svelte` — 동일 분기 로직
- [x] `frontend/src/routes/select-project/+page.svelte` (신규) — `/api/auth/projects/recent` 카드 그리드 UI (이름·프로젝트ID·조직·액세스시기), 클릭 → `setProject` → `/dashboard`

### 56.3 검증

```bash
npm run lint:backend   # All checks passed
npx svelte-check       # 변경 파일 오류 없음 (기존 오류는 무관)
```

수동:
1. `localStorage.afterglow_auth.projectId = null` → 새로고침 → `/select-project` 자동 진입 확인
2. 다중 프로젝트 계정 로그인 → `/select-project` 진입, 카드 클릭 → `/dashboard` 전환 확인
3. 단일 프로젝트 계정 로그인 → `/dashboard` 직행 확인
- GPU 빌드 검증 (Builder VM은 CPU flavor 가정)

---

