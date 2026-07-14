## Why

클래스 다이어그램의 타입 표기 정규화 표가 같은 Mermaid/소스 pair를 한 block 안에 반복해 표시한다.

## What Changes

- 각 Mermaid block의 정규화 표에서 같은 `(Mermaid 표기, 소스 표기)` pair를 최초 등장 순서로 한 번만 표시한다.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- 클래스 다이어그램 정규화 표가 block-local 중복 없이 표시된다.

## Impact

- `docs/class-diagrams/**` 문서 생성 결과만 변경한다.
