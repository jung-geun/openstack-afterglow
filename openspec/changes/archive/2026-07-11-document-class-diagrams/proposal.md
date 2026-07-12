## Why

운영 코드의 이름 있는 타입과 정적 관계를 현재 저장소에서 탐색할 수 있는 클래스 다이어그램으로 문서화한다. 백엔드와 프론트엔드 경계를 함께 보이게 해 유지보수자가 구현 구조를 빠르게 파악할 수 있게 한다.

## What Changes

- `docs/class-diagrams/` 아래에 의미 있는 운영 소스 경로를 미러링한 Mermaid `classDiagram` 문서를 생성한다.
- 각 문서에 타입 책임, 포함 파일, 멤버 요약, 정적 관계 근거와 Mermaid 표기 정규화를 기록한다.
- 전체 아키텍처 계층도와 모든 문서 링크를 제공하는 `INDEX.md`를 생성한다.
- 생성 범위와 Mermaid 렌더링을 검증하고, 애플리케이션 소스는 수정하지 않는다.

## Capabilities

### New Capabilities

- 운영 코드의 이름 있는 타입을 원본 경로별 Mermaid 클래스 다이어그램으로 탐색한다.

### Modified Capabilities

- None.

## Impact

- 영향을 받는 tracked 파일은 `docs/class-diagrams/**`와 이 OpenSpec 작업 기록뿐이다.
- 테스트 전용 타입, 익명 inline Props, generated/dependency/assets/templates 및 타입 0개 경로는 포함하지 않는다.
- 애플리케이션 런타임 동작과 API 계약은 변경하지 않는다.
