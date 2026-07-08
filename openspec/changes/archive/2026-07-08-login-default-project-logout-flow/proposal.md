# login-default-project-logout-flow

## Goal
기본 프로젝트가 있는 로그인은 프로젝트 선택 단계를 건너뛰고, 로그아웃은 확인 후 명확한 완료 피드백을 제공한다.

## Scope
- 로그인/GitLab 콜백 성공 응답의 project_id 또는 default_project_id를 공통 redirect 결정 로직으로 처리한다.
- GitLab 콜백 응답에 접근 가능한 default_project_id를 채워 frontend가 즉시 대시보드로 이동할 수 있게 한다.
- 헤더와 프로젝트 선택 화면의 로그아웃 버튼에 확인 dialog를 붙이고 확인 후 로그인 화면에서 로그아웃 완료 alert를 표시한다.
- backend/frontend focused regression tests를 추가한다.
