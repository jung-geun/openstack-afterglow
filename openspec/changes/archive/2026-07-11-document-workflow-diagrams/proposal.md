## Why

현재 경로별 클래스 다이어그램은 개별 타입 구조를 설명하지만, 상위 모듈 간 연결과 frontend 사용자 작업의 호출 순서를 빠르게 파악하기 어렵다.

## What Changes

- 상위 backend/frontend 문서에 하위 모듈 관계를 요약하는 계층 다이어그램을 추가한다.
- VM, Drover K3s, load balancer, network/router, volume/Manila, object storage frontend 흐름을 Mermaid sequence diagram과 시나리오 클래스 다이어그램으로 문서화한다.

## Capabilities

### New Capabilities

- 모듈 계층 관계와 주요 frontend 리소스 생성·관리 흐름을 문서에서 탐색한다.

### Modified Capabilities

- 기존 클래스 다이어그램 문서가 하위 모듈과 사용자 작업 흐름으로 연결된다.

## Impact

- `docs/class-diagrams/**` 및 이 OpenSpec 작업 기록만 변경한다.
