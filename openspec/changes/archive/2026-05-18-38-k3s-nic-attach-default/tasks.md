## 34. k3s NIC attach 버그 수정 — default route 탈취 / OCCM LB 오라우팅 (2026-05-18)

### 34.1 동기

k3s 클러스터에 NIC를 추가(attach)하면 두 가지 운영 장애 발생:
- **버그 1**: 신규 NIC가 더 낮은 metric의 default route를 받아 기존 primary NIC의 default route 탈취 → 클러스터 통신 단절
- **버그 2**: cloud-provider-openstack(OCCM)이 신규 NIC IP를 NodeInternalIP로 채택 → LoadBalancer endpoint 오라우팅, 내부 서비스 접근 불가

### 34.2 수정 내용

- [x] `backend/app/templates/k3s_server.yaml.j2` — secondary NIC netplan에 `dhcp4-overrides: {use-routes: false, use-dns: false}` + `optional: true` 추가, kubelet `--node-ip=${SERVER_IP}` 주입
- [x] `backend/app/templates/k3s_agent.yaml.j2` — 동일 netplan secondary NIC 규칙 적용
- [x] `backend/app/templates/occm/cloud_config.conf.j2` — `[Networking]` 섹션에 `internal-network-name={{ primary_network_name }}` 추가
- [x] `backend/app/services/k3s_cloudinit.py` — OCCM 렌더에 `primary_network_name` 전달 (Neutron network name lookup), server cloud-init에 `server_ip` 결정적 주입
- [x] `backend/tests/test_k3s_occm.py` (신규) — cloud.conf `internal-network-name` 포함 검증, 빈 network_id 폴백 검증

### 34.3 검증

- [x] 149개 백엔드 테스트 통과
- [x] `npm run lint:backend` 통과
- [ ] 실 환경: NIC attach 후 `ip route` default 불변 확인, `kubectl get nodes -o wide` INTERNAL-IP가 primary NIC IP인지 확인

---

