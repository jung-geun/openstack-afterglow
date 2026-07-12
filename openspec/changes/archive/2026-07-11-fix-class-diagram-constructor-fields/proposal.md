## Why

클래스 다이어그램이 keyword-only 생성자 인자를 직접 대입한 필드의 타입을 `Any`로 표시한다.

## What Changes

- Python 생성자 field inference가 positional, keyword-only, vararg 및 kwargs 파라미터의 annotation을 사용한다.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- 생성자 주입 필드가 실제 parameter type으로 문서화된다.

## Impact

- `docs/class-diagrams/**` 생성 결과만 수정한다.
