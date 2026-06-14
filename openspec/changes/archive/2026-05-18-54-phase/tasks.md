## Phase 53 — Phase 52 후속 프로덕션 버그 5건 수정

### Phase 53a — /dashboard/usage-report 요청 폭주 차단

- [x] usage-report `$effect` untrack 래핑 — Svelte 5 무한 루프 차단
- [x] intervalOptions에 300초 추가 (localStorage 복원 강등 방지)
- [x] /api/dashboard/usage-report 응답에 `Cache-Control: private, max-age=60` 추가
- [x] /api/dashboard/metrics/trend `range=24h` 지원 (step=300, flavor-relative PromQL)
- [x] test_dashboard_usage_report.py Cache-Control 헤더 검증 추가
- [x] test_dashboard_usage_spark.py 신규 5케이스

### Phase 53b — /admin/instances 상단 KPI 응답 스키마 정렬

- [x] /admin/instances/health 응답에 total/active/error/with_alerts/gpu_count 5필드 추가
- [x] _is_gpu_flavor() 헬퍼 (original_name 기반 GPU 감지)
- [x] 기존 items/count 호환 유지
- [x] test_admin_dashboard.py KPI 5필드 검증 케이스 추가

### Phase 53c — /dashboard/usage 24h Spark 카드 연결

- [x] dashboard/usage/+page.svelte placeholder 제거 → Spark 컴포넌트 + PromQL 실데이터 연결
- [x] vCPU/RAM flavor-relative %, 네트워크 KiB/s 표시
- [x] prometheus_available=false 시 "메트릭 수집 미설정" 안내

### Phase 53d — /admin/identity 역할 권한 부족 안내 + 상세 테마 통일

- [x] _collect partial_reasons 필드 추가 (insufficient_privileges / connection_error 분류)
- [x] admin/identity/+page.svelte partial 경고 배지 표시
- [x] 상세 4개 페이지(users/projects/groups/roles) md:p-8 → md:p-6 정렬
- [x] test_admin_dashboard.py partial_reasons 검증 케이스 추가

### Phase 53e — /dashboard/topology 서버측 project_id 필터링

- [x] _fetch_topology_sync project_id 파라미터 추가 (user scope 필터)
- [x] 인스턴스: 현재 프로젝트만, 네트워크: 자기 프로젝트 + external + shared, 라우터: 자기 프로젝트만
- [x] get_topology → _fetch_topology_sync(project_id=pid) 전달
- [x] test_topology.py 신규 5케이스

### Phase 53f — 검증

- [x] pytest 36 passed (test_admin_dashboard + test_dashboard_usage_report + test_dashboard_usage_spark + test_topology)
- [x] alert()/confirm() 잔존 0건, 비용/요금 0건, Nova/Cinder/Manila/Neutron(dashboard) 0건
- [x] npm run check baseline 유지

### Phase 53g — Overview 사용률 카드 Prometheus 통합

**목표**: `/dashboard` Overview의 VCPU/메모리/스토리지 카드를 Prometheus 실데이터로 연결 + range 토글 추가.

**스토리지 의미**: 인스턴스 root fs 사용률 % (node_exporter `node_filesystem_*`) — Cinder 볼륨 GB **아님**. 향후 Cinder 볼륨 추세는 openstack-exporter 도입 시 별도 Phase에서 다룸.

- [x] `backend/app/api/common/dashboard.py` — `/metrics/trend` 엔드포인트 전면 재작성
  - range=24h|7d|14d 지원 (기존 24h|14d에서 확장). step: 24h=300s, 7d=3600s, 14d=6h
  - vCPU/Memory: 모든 range에서 동일 libvirt flavor-relative % 식 (24h range-별 분기 제거)
  - Storage: `node_filesystem_avail/size_bytes{project_id="…",mountpoint="/"}` root fs 사용률 % (cinder_volume_capacity_bytes 제거)
  - Network: `libvirt_domain_interface_stats_*` KiB/s — 응답에 별도 `network` 필드로 분리 (Phase 53c 버그: storage slot에 네트워크 데이터 혼입 → 수정)
  - NaN 가드: `_safe_query`에서 `math.isnan` 포인트 제거 (인스턴스 0개 시 available 오판 방지)
  - Redis 캐시: `cached_call(key, ttl, fn)` — TTL 24h=15s, 7d=120s, 14d=300s
  - `?refresh=true` 쿼리스트링으로 캐시 강제 무효화
- [x] `backend/tests/test_dashboard_usage_spark.py` — 기존 5케이스 assertion 갱신 + 신규 7케이스
  - network 필드 분리 확인, 7d step=3600 검증, node_filesystem expr 확인, invalid range 400, NaN 필터, Redis 캐시 히트 확인
- [x] `frontend/src/lib/components/dashboard/overview/RangeToggle.svelte` — 신규 segmented control (24h/7d/14d, aria-pressed, 화살표 네비)
- [x] `frontend/src/routes/dashboard/+page.svelte` — range 토글 + fetchTrend() 분리
  - range 상태 localStorage 영속 (`dashboard-overview-range`, 기본 14d)
  - range 변경 시 5개 API 재호출 없이 trend만 부분 재조회
  - 카드 라벨 동적 (`vCPU 사용률 (${range})` 등), 스토리지 라벨 "디스크 사용률"로 명시
  - 카드 별 available 체크 → "수집 대기 중" 문구 (prometheus_available=true이나 특정 카드만 빈 경우)
- [x] `frontend/src/routes/dashboard/usage/+page.svelte`
  - Phase 53c 잔존 버그 수정: 네트워크 카드가 `storage.data`를 참조하던 것 → `network.data`로 정정
  - 디스크 사용률 카드 신규 추가 (24h 그룹, 4번째)
  - 14d 추세 placeholder 연결 — `trendData14d` 별도 조회, vCPU/RAM/디스크 mini-grid
- [x] pytest 38 passed, tsc --noEmit 오류 0건

### Phase 53h — Overview 사용률 카드 표시 회귀 정정

- [x] vCPU/RAM PromQL을 node_exporter 기반으로 전환
  - 근본 원인: libvirt scrape job이 Afterglow Prometheus configmap에 없어 `libvirt_domain_info_*{project_id="…"}` 가 빈 시리즈 반환
  - 수정: `node_cpu_seconds_total{mode="idle"}` + `node_memory_MemAvailable/MemTotal_bytes`
  - **의미 변경**: flavor-relative % → guest OS 실제 사용률 % (어떤 인스턴스가 무거운지 판단하는 목적에 더 정확)
- [x] 카드 레이아웃 3행 재구성
  - 헤더 우측: 현재값 (시리즈 마지막 포인트, `text-xl font-semibold tabular-nums`)
  - Spark height 44 → 72 (카드 빈 공간 해소)
  - 하단: `min X% · max Y%` 메타 행
- [x] pytest 14 passed (신규 2건: `test_trend_vcpu_uses_node_cpu_expr`, `test_trend_memory_uses_node_memory_expr`)

### Phase 53i — Overview 사용률 카드 libvirt_exporter 통합 + 그래프 폭 정정

- [x] kolla `globals.afterglow.sample.yml` — `enable_prometheus_libvirt_exporter: "yes"` + `prometheus_libvirt_exporter_port: 9177` 추가
  - 운영자: `kolla-ansible -i inventory reconfigure -t prometheus` 필요
- [x] Prometheus configmap — `instances-libvirt` scrape job 추가 (http_sd → `/api/sd/prometheus/libvirt-targets`)
- [x] Afterglow SD — `/api/sd/prometheus/libvirt-targets` 신설 (`_collect_libvirt_targets`: Nova hypervisors 목록)
- [x] 설정 동기화 — `libvirt_exporter_port = 9177` (`config.py` / `config.toml.example` / `generate_k8s.py`)
- [x] dashboard.py PromQL 교체
  - vCPU: `libvirt_domain_info_cpu_time_seconds_total * on (domain) group_left(instance_id) libvirt_domain_openstack_info{instance_id=~"…"}` (UUID regex 조인)
  - RAM: `libvirt_domain_memory_stats_used_percent` 평균 + 동일 조인
  - 디스크: `node_filesystem_*` 유지 (libvirt에 디스크 사용률 메트릭 없음)
  - 네트워크: `libvirt_domain_interface_stats_*` + UUID regex 조인
  - 빈 프로젝트 early-return — PromQL 호출 0회 + prometheus_available=false
- [x] **커버리지 개선**: node_exporter 미설치 인스턴스(BIO, SYSTEM 등)도 vCPU/RAM 데이터 표시 (kolla reconfigure 후)
- [x] 카드 그래프 폭 정정: `<Spark … class="w-full" />` 로 좌→우 전체 채움
- [x] pytest 15 passed (신규: `test_trend_empty_project_skips_prometheus`)

### Phase 53j — Overview 디스크 카드 libvirt_exporter 가용성 조사 + fallback UX 정정

- [x] `inovex/prometheus-libvirt-exporter` v2.3.1 메트릭 전수 조사
  - `libvirt_domain_block_stats_capacity_bytes`: 정적값(= flavor root_disk), 실제 점유율 미반영
  - `libvirt_domain_block_stats_read/write_bytes_total`: I/O 처리량 카운터, 공간 점유와 무관
  - `allocation_bytes`/`physical_bytes`: exporter 의도적 미노출 (v2.3.1까지 변경 없음)
  - `libvirt_storage_pool_allocation_bytes`: 풀 단위 합계, 인스턴스별 분해 불가
- [x] **결론**: libvirt_exporter 단일 소스로 인스턴스별 디스크 사용률 % 산출 불가 → 디스크 카드는 `node_filesystem_*` 의존 유지
- [x] fallback UX 정정: `prometheus_available=true` + storage `available=false` 시 "수집 대기 중" 대신 "node_exporter 미설치" 메시지 명시
- [x] 후속(Phase 미정): QEMU Guest Agent 기반 디스크 메트릭 pipeline 검토 필요

### Phase 53k — 사용량 페이지 상단 카드 충실화 + 인스턴스별 실 사용률

- [x] 상단 4 카드(vCPU/RAM/디스크/네트워크) — Overview 3-row 패턴 통일: current값 + `class="w-full"` Spark + min·max 푸터
- [x] 스토리지 카드 Phase 53j fallback 메시지("node_exporter 미설치") 적용
- [x] 백엔드 `/api/dashboard/usage-stats` — per-instance `cpu_pct`/`ram_pct` 추가
  - libvirt PromQL 2건(`query_instant_multi`) + UUID regex 조인 (`asyncio.gather` 병렬)
  - Prometheus 미가용 시 silent fallback → 두 필드 `null`
- [x] 상위 인스턴스 테이블 VCPU/RAM bar 의미 교체: 프로젝트 quota 대비 → 인스턴스 실 사용률 0~100%
  - 데이터 없는 인스턴스: "—" 텍스트 + 빈 bar
- [x] 하단 "14일 추세" + "볼륨 분포" 섹션 제거 (`trendData14d` state + fetch 정리)
- [x] pytest 신규 케이스 4건 통과 (live usage 주입 / PromUnavailable fallback / 누락 UUID / 빈 프로젝트)

### Phase 53l — Admin 인스턴스 GPU VM 카운트 0 버그 수정

- [x] `admin_dashboard.py` `_is_gpu_flavor` 강화: `extra_specs`(`pci_passthrough:alias`, `:category`) + `id` fallback
- [x] Nova `/servers/detail` 호출에 `OpenStack-API-Version: compute 2.53` 헤더 추가 (기본 2.1에서는 `original_name` 미포함)
- [x] pytest 신규 5건 통과 (original_name 검출 / pci alias 검출 / audio alias 무시 / CPU 플레이버 0 / 마이크로버전 헤더 송신)

### Phase 53m — Quota -1 → "무제한" 일관 표기

- [x] `QuotaBar.svelte` — `limit === -1` 시 raw `-1` 대신 `무제한` 텍스트 표시 (dashboard 쿼터 사용률 카드 Floating IP 등 일괄 처리)
- [x] `DashboardStatTiles.svelte` — 블록 볼륨 / Floating IP 타일: limit=-1 시 `/ 무제한` 단위 표시
- [x] `VolumeSummaryCards.svelte` — 총 할당 용량 / 볼륨 개수 카드: limit=-1 시 `/ 무제한 GB` / `/ 무제한` 표기
- [x] `QuotaDonut.svelte` — limit=-1 시 `used/무제한` 표기 (limit>0 가드 우회 분기 추가)
- [x] 백엔드 변경 없음 (OpenStack 표준 -1 의미 보존)

### Phase 53n — 사용량 페이지 기간 버튼 trend API 연동

- [x] trend API 호출을 `range=24h` 고정 → 선택된 period 기반 동적 호출
  - `30d` 선택 시 trend API 최대 범위(14d)로 fallback (`trendRange` $derived)
- [x] 상단 4개 카드 레이블을 `trendRange` 기반 동적 표시 (예: `vCPU 7d 추세`)

### Phase 53o — Drover 상세 페이지 6-탭 구조 + K8s 워크로드 조회·기본 액션

**목표**: `/dashboard/drover/[id]` 를 6개 탭으로 재구성하고 누락된 워크로드 API/UI 를 추가한다.

**탭 구성**: 메인 / ConfigMap / Secret / Service / Deployment·RS / Pod

**백엔드**
- [x] `backend/app/models/k3s.py` — 신규 Pydantic 모델 8개 (ContainerStatus, PodInfo, ServicePort, ServiceInfo, DeploymentInfo, ReplicaSetInfo, ScaleDeploymentRequest, PodLogResponse)
- [x] `backend/app/services/k3s_kube.py` — K8s API 헬퍼 8개 + 정규화 함수 4개 (list_pods, list_services, list_deployments, list_replicasets, get_pod_log, delete_service, restart_deployment, scale_deployment)
  - Pod 로그: `text/plain` 응답 → `resp.text` 직접 반환 (`_raise_k8s_error` 우회)
  - Deployment restart: `Content-Type: application/strategic-merge-patch+json` 헤더
  - Scale: `PUT .../scale` + `autoscaling/v1` Scale 객체
- [x] `backend/app/api/k3s/pods.py` — GET /pods, DELETE /pods/{name}, GET /pods/{name}/log
- [x] `backend/app/api/k3s/k3s_services.py` — GET /services, DELETE /services/{name}
- [x] `backend/app/api/k3s/workloads.py` — GET/restart/scale deployments, GET replicasets
- [x] `backend/app/api/k3s/__init__.py` — 3개 라우터 등록
- [x] `backend/app/main.py` — 3개 라우터 include
- [x] `backend/tests/test_k3s_workloads.py` — pytest 12건 통과 (헬퍼 정규화 4건 + 엔드포인트 8건)

**프론트엔드**
- [x] `frontend/src/lib/types/k3s.ts` — ContainerStatus, PodInfo, PodLogResponse, ServicePort, ServiceInfo, DeploymentInfo, ReplicaSetInfo 타입 추가
- [x] `frontend/src/lib/api/k3sWorkloads.ts` — 신규 API 클라이언트 (pods/services/deployments/replicasets/log/restart/scale)
- [x] `frontend/src/lib/stores/k3sClusterDetailController.svelte.ts` — 신규 state·메서드 추가: activeTab, pods/services/deployments/replicasets, loadPods/Services/Deployments, removePod/Svc, rolloutRestartDeployment, scaleDeploymentTo, fetchPodLog; selectedNamespace setter 워크로드 캐시 무효화
- [x] `K3sClusterTabs.svelte` (신규) — 6탭 헤더 (ServiceTabs 패턴)
- [x] `K3sClusterMainPanel.svelte` (신규) — 기존 카드 묶음
- [x] `K3sClusterServicesCard.svelte` (신규) — Service 목록 + 삭제
- [x] `K3sClusterDeploymentsCard.svelte` (신규) — Deployment + ReplicaSet 표 + restart/scale
- [x] `K3sClusterPodsCard.svelte` (신규) — Pod 목록 + 삭제 + 로그
- [x] `K3sPodLogOverlay.svelte` (신규) — Pod 로그 모달 (container 선택, tail_lines 토글)
- [x] `K3sScaleModal.svelte` (신규) — Deployment replicas +/- modal
- [x] `K3sClusterDetailPanel.svelte` — 탭 기반 레이아웃으로 리팩토링 (세로 스택 → 탭 분기)
- [x] `frontend/src/routes/dashboard/drover/[id]/+page.svelte` — `?tab=` 쿼리 파라미터 URL 동기화

