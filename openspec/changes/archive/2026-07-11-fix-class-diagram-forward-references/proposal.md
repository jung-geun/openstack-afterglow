## Why

Python string forward references가 Mermaid 타입 표기에 quote를 남기고 관계 해석에서 누락된다.

## What Changes

- forward-reference quote를 제거하고 문자열 annotation 내부 named type을 관계 후보로 수집한다.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- Python forward reference의 타입 표기와 관계 문서화가 정확해진다.

## Impact

- `docs/class-diagrams/**` 생성 결과만 변경한다.
