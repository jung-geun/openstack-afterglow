## Why

현재 k3s 노드는 Ubuntu 22.04/24.04(가변 인프라) 기반이라 드리프트·패치 일관성 문제가 있다. Fedora CoreOS(불변 인프라, rpm-ostree 원자적 업데이트)로 전환해 재현성과 보안을 높인다.

## What Changes

- k3s 마스터/워커 노드 이미지를 Fedora CoreOS로 전환
- cloud-init → Ignition(FCOS) provisioning 경로 정비
- 기존 cloud-init 템플릿(k3s_server/agent)과의 호환 또는 대체 전략 확정

## Impact

`backend/app/services/k3s_*`, `backend/app/templates/k3s_*` provisioning 경로. 기존 Ubuntu 경로와 병행/대체 여부는 design 단계에서 결정.
