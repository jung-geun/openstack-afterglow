# public-cloud-landing-page

## Goal
Afterglow Cloud를 설명하는 공개 메인 페이지를 루트 경로에 제공하고, 콘솔 접속과 로그인 화면을 분리한다.

## Scope
- `/`를 공개 랜딩 페이지로 전환한다.
- 기존 로그인 폼과 GitLab 로그인 시작 흐름을 `/login`으로 이동한다.
- 보호된 콘솔 접근과 401 세션 만료는 `/login`으로 보낸다.
- 명시적 로그아웃은 `/` 랜딩으로 유지한다.
- 랜딩/인증 route source-contract 테스트와 design visual-debt 검증을 갱신한다.
