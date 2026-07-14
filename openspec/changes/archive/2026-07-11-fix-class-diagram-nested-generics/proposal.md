## Why

Python nested generic annotation이 Mermaid 표기에서 바깥 generic을 잃는다.

## What Changes

- Python annotation AST를 재귀 렌더링해 nested generic, union, literal, forward reference를 보존한다.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- 클래스 다이어그램 Python 타입 표기가 nested generic 구조를 보존한다.

## Impact

- `docs/class-diagrams/**` 생성 결과만 수정한다.
