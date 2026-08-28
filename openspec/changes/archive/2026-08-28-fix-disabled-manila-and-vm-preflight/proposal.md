# 비활성 Manila 호출과 VM 배치 사전검증 수정

## 목표

비활성화된 Manila API를 프론트엔드가 호출해 404를 발생시키는 문제를 제거하고, VM 생성 전 필수 배치 정책 검증 실패가 일반 500으로 노출되는 문제를 명확한 서비스 구성 오류로 처리한다.

## 현재 문제

- 배포의 `services.manila=false`이면 백엔드는 `/api/v1/file-storage` 라우터를 mount하지 않지만 VM 생성 스토어는 파일 스토리지 목록을 무조건 요청한다.
- command palette는 section 단위 서비스 조건을 잃어 비활성 서비스 route로 이동할 수 있다.
- `POST /api/v1/instances/async`는 SSE 응답을 만들기 전에 기본 네트워크와 compute/Cinder availability-zone 정책을 해석한다. 필수 정책이 없거나 유효하지 않으면 예외가 전역 500 처리기로 빠진다.
- legacy 정책 importer는 현재 `cinder.default_volume_availability_zone`을 수집하지 않아 새 cutover에서 해당 정책을 seed할 수 없다.

## 변경 범위

- VM 생성 옵션 로더가 공개 site config의 Manila 활성 상태를 존중한다.
- command palette가 item 및 section 서비스 조건을 보존한다.
- VM 생성 사전검증의 예상 가능한 리소스 정책 오류를 안전한 503 응답으로 변환한다.
- legacy `nova.default_availability_zone`을 compute와 volume 기본 AZ 정책 모두에 seed하도록 importer를 보완한다.
- 각 동작에 focused regression을 추가한다.

## 비범위

- Manila가 실제 운영 대상이면 `afterglow_service_manila_enabled=true`로 바꾸고 Kolla reconfigure하는 운영 작업은 코드 변경과 별개다.
- 누락된 운영 DB 정책을 추측해 자동 삽입하지 않는다. importer 또는 관리자 리소스 정책 UI를 통해 검증된 값만 저장한다.
