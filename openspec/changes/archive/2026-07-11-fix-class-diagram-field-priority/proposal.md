## Why

12-field 요약이 repository named-type 관계 필드보다 일반 필드를 우선한다.

## What Changes

- 필드 선택에서 ID 계열 다음에 repository named-type annotation을 우선한다.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- 클래스 다이어그램이 관계형 필드를 멤버 요약에 보존한다.

## Impact

- `docs/class-diagrams/**` 생성 결과만 변경한다.
