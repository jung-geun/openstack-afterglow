## Why

랜딩이 light theme을 지원하게 되었지만, 4:3 dark SVG plate를 더 세로인 figure에서 `contain`으로 보여 주는 hero·overview collage가 light surface 색을 letterbox로 노출한다. 다크 artwork가 밝은 띠 위에 떠 보여 editorial media가 분리된다.

## What Changes

- hero와 overview collage의 SVG figure backdrop을 theme과 무관한 dark editorial media canvas로 고정한다.
- 기존 SVG 전체를 보이는 `object-fit: contain` 동작, dark/light surface, 반응형 crop을 모두 확인한다.

## Capabilities

### New Capabilities

- 없음.

### Modified Capabilities

- light theme 공개 랜딩의 hero·overview SVG media surface.

## Impact

- `frontend/src/lib/components/landing/LandingPage.svelte`의 figure surface CSS와 focused landing visual verification.