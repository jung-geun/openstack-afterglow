## Why

관리자 네트워크 상세 화면은 서브넷의 CIDR과 게이트웨이만 보여 주어 IP 고갈, 포트 점유, DHCP 배치, 실제 바인딩 노드를 확인하려면 OpenStack CLI/API를 별도로 사용해야 한다. 관리자가 서브넷 단위의 운영 상태를 한 화면에서 추적할 수 있어야 한다.

## What Changes

- 관리자 전용 서브넷 상세 API를 추가해 서브넷 기본 정보, allocation pool 시작/끝, 해당 서브넷에 할당된 IP, 포트, Neutron binding host를 반환한다.
- DHCP 포트와 네트워크를 호스팅하는 DHCP agent를 host 기준으로 연결해 agent IP와 배치 노드를 반환한다.
- DHCP agent scheduler extension이 없는 OVN 등의 환경에서는 핵심 서브넷/포트 데이터를 유지하고 agent 데이터 가용 여부를 명시한다.
- `/admin/subnets/{id}` 상세 화면을 추가하고 관리자 네트워크 상세의 서브넷 이름을 이 화면으로 연결한다.
- 모바일·태블릿·데스크톱에서 동일한 정보를 유지하며 운영 데이터 표는 `TableShell`의 가로 스크롤 계약을 따른다.

## Capabilities

### New Capabilities

- **Administrator subnet operations view**: allocation pool, 할당 IP, 사용 포트, DHCP agent IP/배치 노드, 각 IP의 Neutron 실제 binding host를 관리자에게 제공한다.

### Modified Capabilities

- **Administrator network detail**: 서브넷 요약에서 별도 서브넷 상세 화면으로 이동할 수 있다.

## Impact

- Backend: `backend/app/models/storage.py`, `backend/app/services/neutron.py`, `backend/app/api/identity/admin.py`, 네트워크 API/서비스 테스트.
- Frontend: 네트워크 타입, 관리자 서브넷 상세 route, 네트워크 서브넷 링크, route/component 테스트.
- API: 관리자 인증이 필요한 `GET /api/v1/admin/subnets/{subnet_id}`가 추가된다. 일반 사용자 API 응답에는 관리자 전용 binding/agent 정보가 노출되지 않는다.
- OpenStack: Neutron `binding`, `agent`, `dhcp_agent_scheduler` 확장을 사용하며 optional agent 조회 실패는 명시적인 부분 가용 상태로 표현한다.
