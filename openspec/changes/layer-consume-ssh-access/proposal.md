## Why

레이어 소비 VM은 현재 부팅만 되고 SSH 접속 경로를 제어할 수 없다. 운영자가 특정 키로 접속 가능한 소비 VM을 바로 확인할 수 있어야 한다.

## What Changes

- admin layers 소비 VM 생성 폼에 선택적 키페어/SSH 사용자 입력 추가
- 요청자 scoped keypair의 public key를 backend에서 조회해 service-project 소비 VM cloud-init에 주입
- 선택된 SSH 사용자 또는 기본 사용자에 authorized key가 들어가도록 consume cloud-init 확장

## Impact

`backend/app/api/union/layer_ops.py`, `backend/app/services/layer_build.py`, `frontend/src/routes/admin/layers/+page.svelte`, 관련 backend tests. 기존 consume VM 생성 흐름은 유지하고 SSH 접근만 확장한다.
