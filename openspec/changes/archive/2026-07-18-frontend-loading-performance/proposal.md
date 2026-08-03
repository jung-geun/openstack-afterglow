## Why

관리자·사용자 라우트의 초기 데이터 로딩이 페이지별로 분산되어 있어 같은 GET이 mount와 auto-refresh에서 중복되거나, 독립 요청이 waterfall로 이어지거나, 선택하지 않은 탭·모달 데이터가 핵심 콘텐츠와 경쟁한다. 이 때문에 백엔드 응답이 빠르더라도 첫 콘텐츠가 늦게 보이고 다단계 작업에서 다음 화면의 대기가 반복된다.

## What Changes

- 동일 scope의 일반 GET은 진행 중 요청만 공유하고, 명시적으로 선로딩한 GET만 짧은 TTL로 재사용하는 token/project/mock-safe API 계약을 추가한다.
- auto-refresh와 별도 mount/effect가 같은 loader를 중복 호출하는 관리자·사용자 라우트를 단일 초기 owner로 정리한다.
- 독립 요청은 같은 turn에 시작하고 primary/optional 영역을 독립적으로 표시하며, 실제 데이터 의존성만 순차 처리한다.
- 숨은 탭·모달 catalog·다음 marker 페이지·topology detail은 idle/hover/focus 기반의 안전한 GET prefetch로 이동한다.
- 변경 전후 동일 조건에서 초기 요청 수, 요청 overlap, primary loading 해제 시간을 비교한다.

## Capabilities

### New Capabilities

- Token/project/mock revision으로 격리된 bounded GET prefetch와 in-flight request coalescing
- Pagination·create action·topology intent 기반의 취소 가능한 선로딩
- 관리자/사용자 공통 route loading performance baseline 및 회귀 검증

### Modified Capabilities

- Auto-refresh 초기 실행 ownership
- Admin services/libraries/identity/monitoring route loading
- User instance/detail/object-storage/usage/notifications/K3s/library route loading
- Project-name 및 Grafana shared cache scope

## Impact

Frontend API client, mock transport/state, shared refresh/cache utilities, UI Button/Pagination event contract, 다수의 admin/dashboard route와 해당 Vitest가 변경된다. Backend endpoint나 payload는 변경하지 않는다. 모든 호출은 기존 `/api/v1` 계약, 인증·프로젝트 격리, mockup 무실API 보장을 유지한다.
