## 60. 프로젝트 전환 시 JWT rescope + 로딩 스켈레톤 (2026-05-24)

### 60.1 목표

상단 `ProjectSelector` 드롭다운에서 프로젝트 전환 시 발생하는 두 가지 결함을 수정한다:
1. 간헐적 401 인증 실패 — `selectProject()` 가 JWT rescope 없이 `X-Project-Id` 헤더만 변경, 백엔드 stampede 유발
2. 이전 프로젝트 데이터 잔존 — 전환 후 state 미초기화로 구 데이터가 그대로 표시됨

### 60.2 구현

- [x] `frontend/src/lib/components/ProjectSelector.svelte` — `selectProject()` async 전환, `POST /api/auth/switch-project` 호출로 JWT rescope 후 `setAuth()` atomic 갱신, 전환 중 `disabled` + spinner 처리
- [x] `frontend/src/routes/select-project/+page.svelte` — 동일한 rescope 패턴 적용 (로그인 직후 첫 선택 흐름)
- [x] `frontend/src/routes/dashboard/+page.svelte` — `{#key $auth.projectId}` wrapper로 프로젝트 전환 시 컴포넌트 트리 remount → 기존 `loading && empty` 가드 자동 발동. 사용 추세 카드·시스템 알림 인라인 `animate-pulse` 스켈레톤 추가
- [x] `frontend/src/routes/admin/+page.svelte` — 동일한 `{#key $auth.projectId}` wrapper 적용

---

