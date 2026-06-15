## Implementation Tasks

- [ ] FCOS 베이스 이미지 + Ignition provisioning PoC (단일 노드 k3s 부팅)
- [ ] k3s_server/agent provisioning을 cloud-init ↔ Ignition 분기 처리
- [ ] OCCM/CSI/Barbican KMS 플러그인이 FCOS에서 동작하는지 검증
- [ ] Ubuntu ↔ FCOS 선택 옵션 (인스턴스 생성 시 image 메타 기반 분기)
- [ ] 회귀 테스트: `backend/tests/`에 FCOS provisioning 렌더 검증 추가
