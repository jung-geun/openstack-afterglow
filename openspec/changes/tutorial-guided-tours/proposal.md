# tutorial-guided-tours

## 목표

mockup 모드 기반 인터랙티브 튜토리얼(코치마크 투어)을 추가한다. VM 생성 / 볼륨 생성·관리 / Drover 사용 3개 시나리오를 driver.js 투어로 안내하고, 랜딩 페이지에 "튜토리얼 체험하기" CTA로 진입 흐름을 만든다. 투어는 mockup 모드와 로그인한 실계정 대시보드 양쪽에서 동작한다.

## 범위

- 신규 `frontend/src/lib/tutorial/` — 투어 엔진(driver.js 래퍼), 시나리오 정의, 런처 모달
- 랜딩 페이지 CTA + `?tour=` 쿼리 파라미터 진입
- 기존 컴포넌트에 `data-tour` 앵커 속성 추가 (Sidebar, VM 위저드, 볼륨, Drover)
- mockup 확장: `/dashboard/volumes` 허용 경로, 볼륨 CRUD·위저드 데이터 픽스처, 인스턴스 생성 SSE mock
- 백엔드 변경 없음 (프론트엔드 전용)

## 완료 기준

- 랜딩 → 튜토리얼 진입 → 3개 투어가 mockup 데이터로 끝까지 진행 가능
- `npm run test:all` + `npm run lint:backend` 통과
