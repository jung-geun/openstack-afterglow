## Why

Union Mount(OverlayFS) VM의 마운트 상태·레이어 정합성을 런타임에 관측할 수단이 없다. 마운트 실패/드리프트를 조기 감지할 경량 에이전트가 필요하다.

## What Changes

- VM 내부에서 OverlayFS 마운트 상태(merged/lower/upper/work)와 레이어 digest를 주기 점검
- 기존 health-report 토큰 경로(`instance_health`)로 상태 보고
- 이상 시 대시보드 노출

## Impact

`backend/app/templates/`(health-check 스크립트 확장), `backend/app/services/instance_health.py`, 프론트 인스턴스 상세. 기존 7일 health bearer 토큰 흐름 재사용.
