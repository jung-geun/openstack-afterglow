## 61. 셀프서비스 프로젝트 생성 + 이메일 초대 시스템 (2026-05-25)

### 61.1 목표

일반 사용자가 직접 프로젝트를 생성하고, 이메일로 다른 사용자를 초대할 수 있는 셀프서비스 시스템을 구현한다.

### 61.2 Backend (Phase 1~4)

- [x] `backend/migrations/013_project_self_service.sql` — `project_roles`, `project_invitations` 테이블 DDL
- [x] `backend/app/models/db.py` — `ProjectRole`, `ProjectInvitation` ORM 모델 추가
- [x] `backend/app/database.py` — `create_tables()` idempotent DDL 추가
- [x] `backend/app/config.py` — SMTP 설정 + `frontend_base_url` 필드 추가
- [x] `config.toml.example` — `[smtp]` 섹션 + `frontend_base_url` 문서화
- [x] `generate_k8s.py` — SMTP password를 `render_secret()` 추가
- [x] `backend/pyproject.toml` — `aiosmtplib>=3.0.0` 의존성 추가
- [x] `backend/app/services/email_service.py` (신규) — `send_email()` + `send_invitation_email()` aiosmtplib 구현
- [x] `backend/app/services/project_service.py` (신규) — `create_project_for_user`, `create_invitation`, `accept_invitation`, `decline_invitation`, `is_project_manager`, `promote_to_manager`, `demote_manager`
- [x] `backend/app/api/deps.py` — `require_project_manager` 의존성 추가
- [x] `backend/app/api/identity/projects.py` (신규) — `/api/projects` 라우터 (7개 엔드포인트)
- [x] `backend/app/api/identity/invitations.py` (신규) — `/api/invitations` 라우터 (3개 엔드포인트)
- [x] `backend/app/main.py` — 두 라우터 등록
- [x] `backend/tests/test_project_self_service.py` (신규) — 13개 단위 테스트 전통과

### 61.3 Frontend (Phase 5)

- [x] `frontend/src/lib/types/project.ts` — `ProjectManagerMember`, `ProjectInvitation`, `InvitationInfo` 인터페이스 추가
- [x] `frontend/src/lib/components/projects/CreateProjectModal.svelte` (신규) — 프로젝트 생성 모달
- [x] `frontend/src/routes/select-project/+page.svelte` — "새 프로젝트" 버튼 + CreateProjectModal 연결
- [x] `frontend/src/routes/dashboard/project-settings/+page.svelte` (신규) — 멤버 탭 + 초대 탭
- [x] `frontend/src/routes/invitations/[token]/+page.svelte` (신규) — 초대 수락/거절 공개 페이지
- [x] `frontend/src/lib/components/Sidebar.svelte` — "프로젝트 설정" 링크 추가
- [x] `frontend/src/lib/config/nav.ts` — `projectSettingsNavSection` export 추가
- [x] `frontend/src/lib/config/routes.ts` — `'project-settings'`, `'invitations'` 라벨 추가
- [x] `frontend/src/lib/components/account/ProjectsSection.svelte` — 활성 프로젝트에 "관리" 링크 추가
- [x] `frontend/src/lib/components/ProjectSelector.svelte` — 드롭다운 하단 "새 프로젝트" 버튼 + 모달 연결
- [x] `frontend/src/routes/+layout.svelte` — `/invitations/*` 경로를 auth guard 및 project guard에서 제외, 미니멀 렌더링

---

