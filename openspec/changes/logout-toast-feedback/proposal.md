# logout-toast-feedback

## Goal
로그아웃 완료 메시지를 로그인 폼 내부 alert가 아니라 전역 toast로 표시한다.

## Scope
- 로그아웃 성공 후 로그인 화면으로 돌아가되 `logged_out` query와 로그인 페이지 alert를 제거한다.
- 전역 Toast를 비로그인 상태에서도 렌더해 로그아웃 완료 toast가 유지되게 한다.
- 헤더와 프로젝트 선택 화면 로그아웃 경로 모두 동일한 toast 메시지를 사용한다.
- focused frontend source-contract test를 갱신한다.
