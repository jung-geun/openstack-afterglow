# Tasks

- [x] driver.js 의존성 추가
- [x] 투어 엔진 (`frontend/src/lib/tutorial/engine.ts`) — waitForElement, 라우트 이동, sessionStorage 재개
- [x] 투어 시나리오 정의 (`frontend/src/lib/tutorial/tours.ts`) — vm-create / volume / drover
- [x] 투어 런처 모달 (`frontend/src/lib/tutorial/TutorialLauncher.svelte`) + `+layout.svelte` 마운트 + `?tour=` 처리
- [x] `data-tour` 앵커 속성 추가 (Sidebar, 위저드, 볼륨, Drover)
- [x] 랜딩 페이지 "튜토리얼 체험" CTA
- [x] mockup: `TUTORIAL_ALLOWED_PATHS`에 `/dashboard/volumes` 추가
- [x] mockup: state에 volumes 시드 추가
- [x] mockup: 볼륨 CRUD + 위저드 데이터 픽스처 (transport.ts)
- [x] mockup: 인스턴스 생성 SSE mock (`maybeMockInstanceCreateStream`) + vmCreateStore 연동
- [x] 테스트: engine / transport / state / landing CTA
- [x] 검증: frontend vitest 466개 + backend pytest 2893개 + `lint:backend` 전부 통과, Playwright로 3개 투어 실동작 확인
