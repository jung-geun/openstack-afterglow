## Why

사용자 네트워크 목록의 CIDR 열은 항상 `—`를 렌더링하지만, 네트워크 상세 API는 같은 네트워크의 서브넷 CIDR을 정상적으로 보여 준다. 목록 API 계약이 서브넷 ID만 반환하고 CIDR을 생략해 동일 리소스가 화면마다 다르게 보인다.

## What Changes

- 사용자 네트워크 목록 조회에서 접근 가능한 서브넷을 한 번에 조회하고 network ID별 CIDR 목록을 구성한다.
- `NetworkInfo` 응답에 `cidrs` 배열을 추가한다. 복수 서브넷 네트워크도 손실 없이 모든 CIDR을 반환한다.
- 사용자 네트워크 목록은 하드코딩된 `—` 대신 `cidrs`를 표시하고 CIDR이 없는 네트워크만 `—`를 표시한다.
- 목록 조회는 네트워크별 상세 요청을 만들지 않고 네트워크 1회 + 서브넷 1회의 bulk 조회를 유지한다.

## Capabilities

### New Capabilities

- 없음.

### Modified Capabilities

- **User network inventory**: 네트워크 목록에서 각 네트워크에 연결된 실제 서브넷 CIDR을 확인할 수 있다.

## Impact

- Backend: `NetworkInfo` 모델과 Neutron 목록 직렬화, 관련 단위 테스트.
- Frontend: `Network` 타입과 `NetworksTableCard` CIDR 렌더링, 컴포넌트 회귀 테스트.
- API: `GET /api/v1/networks` 항목에 하위 호환 가능한 `cidrs: string[]` 필드가 추가된다.
