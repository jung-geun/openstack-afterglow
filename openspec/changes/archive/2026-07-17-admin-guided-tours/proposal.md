## Why

관리자 영역에는 사용자 영역의 `driver.js` 기반 페이지별 튜토리얼과 같은 안전한 학습 경로가 없다. 운영 권한이 큰 화면인 만큼 실제 리소스를 변경하지 않으면서 주요 상태, 필터, 탭, 행, 상세 패널을 익힐 수 있는 관리자 전용 안내가 필요하다.

## What Changes

- `AdminSidebar`의 Compute, 스토리지, 라이브러리, 네트워크, 컨테이너, Key Manager, 모니터링, 시스템, Identity 섹션에 각각 한 개의 관리자 튜토리얼을 추가한다.
- 기존 튜토리얼 엔진, 시작 버튼, 사용자별 완료/닫기 상태 API를 확장하고 새 관리자 tour ID 9개를 등록한다.
- 조회·필터·탭·상세 탐색만 단계로 허용하고 생성·수정·삭제·시작·중지 등 상태 변경은 튜토리얼과 관리자 mockup에서 차단한다.
- `?tutorial=admin`이 9개 대표 관리자 화면에서 동작하도록 정확한 경로 허용 목록과 결정적 read-only fixture를 추가한다.
- 로딩·빈 목록·오류·새로고침 재개·뒤로 가기를 포함하는 엔진 및 mockup 회귀 테스트를 추가한다.

## Capabilities

### New Capabilities

- 관리자 주요 9개 섹션의 안전한 페이지별 guided tour
- 9개 대표 관리자 경로의 fixture-backed admin mockup 탐색

### Modified Capabilities

- 튜토리얼 tour ID, 세션 재개, 사용자별 상태 캐시, click-driven 뒤로 가기 계약
- 관리자 mockup navigation allowlist와 비변경 API 안전 경계

## Impact

프론트엔드 튜토리얼 엔진·상태·관리자 레이아웃/페이지/컴포넌트와 mockup state/transport가 변경된다. 백엔드는 튜토리얼 상태 허용 ID만 확장하며 DB 스키마와 API 경로는 바뀌지 않는다. 기존 사용자 튜토리얼과 실제 관리자 서비스/베타 게이트는 유지한다.
