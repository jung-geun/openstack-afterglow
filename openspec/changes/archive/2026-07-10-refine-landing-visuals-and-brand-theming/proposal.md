## Why

공개 랜딩의 공유 데이터 공간, 관측, 레이어·스냅샷, 네트워크 라우팅 비주얼이 각 기능의 실제 역할을 충분히 설명하지 못한다. 헤더 로고와 브라우저 favicon도 현재 테마와 맞지 않는 단일 자산처럼 보이므로, 다크·라이트 surface에서 브랜드 식별성이 떨어진다.

## What Changes

- 공유 데이터 공간, 실험 환경 실행·관측, 레이어·스냅샷 재사용, 라우터 토폴로지를 각각의 실제 워크플로우가 읽히는 텍스트 없는 SVG 비주얼로 개선한다.
- 기존 런타임 `logo_light_path`/`logo_dark_path`와 resolved theme 계약을 재사용해 랜딩 헤더가 배경 대비에 맞는 로고를 선택하게 한다.
- 기존 favicon fallback을 보존하면서 활성 테마에 맞는 favicon href를 갱신한다. 새 backend 설정 필드는 추가하지 않는다.
- 시각 자산 연결, 테마별 로고/favion 선택, 기존 fallback에 대한 집중 회귀 테스트를 추가한다.

## Capabilities

### New Capabilities

- 없음.

### Modified Capabilities

- 공개 랜딩의 워크플로우·제공 단계·네트워크 비주얼 의미 전달.
- 런타임 브랜딩 자산의 테마별 헤더와 favicon 적용.

## Impact

- `frontend/src/lib/components/landing/LandingPage.svelte` 및 정적 landing SVG.
- 루트 route/head 또는 layout의 favicon·runtime branding 연결.
- 관련 frontend component, route, config/theme tests.