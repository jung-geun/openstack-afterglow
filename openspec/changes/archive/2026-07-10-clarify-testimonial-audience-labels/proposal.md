## Why

랜딩의 대상 사용자 그룹이 `연`, `교`, `실`, `GPU`, `API` 같은 축약어·기술 용어로 표시되어, 인용문이 설명하는 실제 사용자와 조직을 식별하기 어렵다. `aria-label`도 대상 사용자 그룹임을 선언하므로 표기와 의미를 일치시켜야 한다.

## What Changes

- VII 인용문 아래의 다섯 레이블을 실제 연구 클라우드 대상인 연구실, 교수자, 연구원, 실습팀, 연구 조직으로 교체한다.
- 고정 원형 5열 레이아웃을 내용 너비의 pill과 자동 줄바꿈 레이아웃으로 바꿔 긴 한국어 레이블을 모든 화면폭에서 읽을 수 있게 한다.
- 전체 레이블과 기존 축약어 부재를 고정하는 랜딩 컴포넌트 회귀 테스트를 추가한다.

## Capabilities

### New Capabilities

- 없음.

### Modified Capabilities

- 공개 랜딩의 VII 대상 사용자 그룹 표기와 반응형 레이아웃.

## Impact

- `frontend/src/lib/components/landing/LandingPage.svelte`의 인용문 마크업·스타일.
- `frontend/src/lib/components/landing/__tests__/LandingPage.test.ts`의 랜딩 콘텐츠 계약.