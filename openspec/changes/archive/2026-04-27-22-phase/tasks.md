## 18. 네트워크 토폴로지 실시간 트래픽 시각화 (Phase 1)

> VM + 네트워크 + LB 기준 instant rate. 라우터는 Phase 2(kolla exporter 활성화 후).

- [x] `backend/app/services/prom_query.py` — `query_instant_multi` 헬퍼 신규 (Prometheus `/api/v1/query` 다중 시계열 instant 파싱)
- [x] `backend/app/services/octavia.py` — `get_lb_stats`, `lb_rate_from_snapshot`, `_lb_snapshot` in-memory dict (Octavia 누적 카운터 차분으로 rate 계산)
- [x] `backend/app/services/neutron.py` — `list_project_compute_ports` 헬퍼 추출 (port → server uuid + network_id 매핑)
- [x] `backend/app/api/network/networks.py` — `GET /api/networks/topology/traffic` 신규 엔드포인트 (VM rx/tx PromQL + 네트워크 합산 + LB Octavia stats 병렬)
- [x] `frontend/src/lib/components/GlobalTopology.svelte` — `traffic` prop, `formatBps`/`trafficColor`/`edgeColor` 유틸, 박스 옆 rx/tx 텍스트, 네트워크 막대 합산 라벨, 엣지 stroke 동적 색상
- [x] `frontend/src/routes/dashboard/network/topology/+page.svelte` — 두 번째 `createAutoRefresh` 15s (traffic 전용) + `<GlobalTopology {traffic} />`
- [x] `backend/tests/test_topology_traffic.py` — 신규 8건 (VM bps ×8, 네트워크 합산, routers={}, no instances 200, PromUnavailable fallback, LB first call 0, LB rate, query_instant_multi 파싱)
- [x] `backend/app/api/network/networks.py` — libvirt-exporter 폴백: `libvirt_domain_interface_stats_*` × `libvirt_domain_openstack_info` 조인으로 node_exporter 미노출 인스턴스(테넌트망 격리) 보강. 4-fan-out 병렬 PromQL, node_exporter 우선
- [x] `frontend/src/lib/components/GlobalTopology.svelte` — Prometheus 데이터 부재 시 인스턴스 엣지 색상을 회색이 아닌 네트워크 색으로 폴백 (`_tRow` null 체크)
- [x] `backend/tests/test_topology_traffic.py` — 신규 3건 (libvirt 폴백, node_exporter 우선순위, PromQL 조인 패턴 검증)
- [x] `backend/app/services/neutron.py` — `list_project_port_map` 신규 함수 (port_id → mac_address / network_id / instance_id 매핑)
- [x] `backend/app/api/network/networks.py` — 멀티-NIC MAC 기반 demux: `libvirt_domain_interface_stats_info` 이중 group_left 조인으로 NIC 단위 `interfaces` 응답 필드 추가, `networks` 합산 정확도 개선, 포트맵 Redis 캐시(ttl_static=300s) 적용
- [x] `backend/app/api/compute/instances.py` — attach_interface / detach_interface / delete_server 에 `port_mac_map` 캐시 무효화 hook 추가
- [x] `backend/tests/test_topology_traffic.py` — 신규 8건 (멀티-NIC demux, single/multi-NIC networks 합산 분기, libvirt 주경로 + node_exporter 보강, libvirt 미스크레이프 윈도, PromQL double group_left 패턴 검증)
- [x] `backend/app/api/compute/instance_metrics.py` — `_build_libvirt_expr` 신규 함수 (6개 메트릭 libvirt 폴백 PromQL, GPU는 None). `_one`/단일 엔드포인트에 순차 폴백(node_exporter 빈 시계열→libvirt 재시도) 적용
- [x] `frontend/src/lib/components/instance/MetricsPanel.svelte` — 데이터 없음 메시지를 "메트릭 없음 (인스턴스 미가동 또는 exporter 미연동)"으로 완화
- [x] `backend/tests/test_instance_metrics.py` — 신규 7건 (cpu/memory/network_rx/disk_read 폴백, node_exporter 우선·폴백 미호출, 양쪽 빈→빈 시계열, libvirt 표현식 단일 시계열 가드)

