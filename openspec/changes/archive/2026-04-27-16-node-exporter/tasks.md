## 12. 인스턴스 관측성 — Node Exporter + 메트릭 가시성

> **목표**: 운영 중인 모든 사용자 VM의 시스템(`node_exporter:9100`) + GPU(`dcgm-exporter:9400`) 메트릭을 외부에서 안정적으로 수집하고, 프로젝트별 Grafana 대시보드로 사용자가 자신의 인스턴스 상태를 직접 확인할 수 있도록 한다. 11.4 `ensure_union_egress_sg` 패턴을 그대로 ingress 변형으로 재사용한다.

> **배경**: GPU DCGM Exporter(섹션 11 끝)는 cloud-init 단으로 자동 설치 완료. Node Exporter는 base 이미지 빌드 트랙에서 사전 설치 예정 (별도 인프라 작업, 본 코드 변경 외). 현재 Prometheus(`monitoring/prometheus.yml`, `deploy/k8s-template/monitoring/prometheus/configmap.yaml`)는 `backend:8000/api/metrics`만 스크래핑하며 VM은 미수집. 사용자 VM에는 fixed IP만 있고 보안 그룹 ingress는 기본 차단 상태.

### 12.1 Node Exporter 사전 설치 (이미지 빌드 트랙 — 본 저장소 외)

- [ ] base qcow2 이미지에 `node_exporter` 바이너리 + systemd unit 사전 설치 (Packer/Diskimage-Builder 빌드 스크립트)
- [ ] `node_exporter --web.listen-address=0.0.0.0:9100` 기본 구성, `--collector.systemd` 활성화
- [ ] 본 저장소 변경: `backend/tests/integration/test_image_metadata.py` 신규 — 이미지 메타데이터에 `monitoring_ready=true` 태그가 있는지 사전 검증 (선택)
- [ ] `backend/app/api/compute/instances.py` 인스턴스 생성 시 이미지 메타에서 `monitoring_ready` 추출하여 SG 자동 적용 분기에 활용 (12.2와 연동)

### 12.2 Monitoring 보안 그룹 자동화 (node_exporter / dcgm_exporter 분리)

11.4의 `ensure_union_egress_sg` 패턴을 ingress 변형으로 재사용. **단일 통합 SG 대신 exporter별 SG 2개로 분리**하여, GPU flavor만 `dcgm_exporter` SG가 attach되도록 한다. auto-attach 트리거 시 `default` SG도 명시적으로 보존한다.

- [x] `backend/app/services/neutron.py` — `_ensure_single_port_ingress_sg` (internal generic) + `ensure_node_exporter_sg(conn, project_id, sg_name="node_exporter", scrape_cidr)` (tcp/9100) + `ensure_dcgm_exporter_sg(conn, project_id, sg_name="dcgm_exporter", scrape_cidr)` (tcp/9400) idempotent 헬퍼. 기존 `ensure_monitoring_ingress_sg` + `_MONITORING_INGRESS_RULES` 제거
  - `scrape_cidr`은 Prometheus 스크래퍼 IP/서브넷에 한정 (0.0.0.0/0 금지)
- [x] `backend/app/config.py` — `monitoring_sg_name` 제거, 신규 `node_exporter_sg_name: str = "node_exporter"`, `dcgm_exporter_sg_name: str = "dcgm_exporter"` 추가
- [x] `backend/app/api/identity/admin_identity.py:create_project` — 두 SG 모두 사전 생성 (각 try/except 비차단)
- [x] `backend/app/api/identity/admin_identity.py:sync_monitoring_sg` — 두 SG 모두 동기화, 응답 `{"sg_names": {"node_exporter": ..., "dcgm_exporter": ...}}`
- [x] `backend/app/api/compute/instances.py:create_instance` + `create_instance_async` — node_exporter는 모든 인스턴스, dcgm_exporter는 GPU flavor만. auto-attach 트리거 시 `default` SG도 명시적 보존. async 경로 `gpu_available` 스코프 픽스 (flavor lookup을 `if resolved_libs:` 위로 끌어올림)
- [ ] `frontend/src/lib/components/VmCreatePanel.svelte` — SG 자동 attach 안내 배지 (후속)
- [x] `backend/tests/test_neutron.py` — generic 5건 + wrapper smoke 2건 (총 7건)
- [x] `backend/tests/test_admin_identity.py` — create_project 두 SG 검증 + sync 엔드포인트 (총 2건)
- [x] `backend/tests/test_instances.py` — non-GPU/GPU/disabled/no-cidr 4건
- [x] `backend/tests/conftest.py` — rate limiter storage reset autouse fixture 추가 (테스트 격리)

### 12.3 Prometheus 스크래핑 — 메인 클러스터 통합 vs 프로젝트별 분리 ✅ Option A 확정

> **결정 확정 (2026-05-15)**: Option A — 단일 Prometheus+Grafana 스택 + `var-project_id` URL 파라미터 기반 테넌트 분리. 운영 단순성, 기존 구현 기준.

#### Option A: 메인 Prometheus + Grafana 단일 인스턴스 + tenant 라벨 분리 (권장)

- 장점: 운영 단일 스택, Grafana org/folder + label-based row-level security로 프로젝트 격리, 비용/리소스 효율
- 단점: 사용자 정의 대시보드 자유도 낮음 (관리자가 템플릿 제공), Prometheus single-tenant 한계
- [ ] `monitoring/prometheus.yml` + `deploy/k8s-template/monitoring/prometheus/configmap.yaml` — `nova_sd` 또는 `http_sd_config` 추가하여 OpenStack VM 자동 발견
- [x] `backend/app/api/common/sd_targets.py` (신규) — `GET /api/sd/prometheus/targets` Prometheus `http_sd` 호환 JSON 응답 (인스턴스 목록 + `instance`, `project_id`, `flavor`, `gpu` 라벨)
  - 인증: 별도 token (스크래퍼 전용), `monitoring_sd_token` 설정값
  - VM의 floating IP가 없어도 fixed IP를 그대로 노출 (스크래퍼가 internal network에 접근 가능하다는 가정)
- [x] `backend/tests/test_sd_targets.py` — 라벨 형식, token 검증, 권한 4건
- [ ] `deploy/k8s-template/monitoring/prometheus/configmap.yaml` — DCGM/Node 스크래핑 잡 추가 (`__meta_*` 라벨 → `project_id`/`instance` 재라벨)
- [x] `deploy/k8s-template/monitoring/grafana/` — provisioning ConfigMaps (datasource + dashboards-provider + dashboards 9종) + volumeMounts + NetworkPolicy (외부 직접 접근 차단)
- [x] `frontend/src/routes/dashboard/observability/+page.svelte` (신규) — Grafana iframe 임베드 + 프로젝트별 URL 자동 생성 (`var-project_id={current}`) + projectId null guard + 프론트엔드 테스트 4건

#### Option B: 프로젝트별 컨테이너 모니터링 스택 (대안)

- 장점: 완전한 격리, 사용자가 자신의 대시보드/알람 자유 구성, BYO Grafana
- 단점: 프로젝트당 Prometheus+Grafana 컨테이너 관리(리소스 비용 N배), 사용자가 docker-compose 운영 필요, 인증/네트워크 설계 복잡
- [ ] `backend/app/templates/monitoring_stack/docker-compose.yml.j2` (신규) — Prometheus + Grafana 한 쌍, 사용자 다운로드 가능
- [ ] `backend/app/api/compute/instances.py` — `GET /api/instances/{id}/monitoring-bundle` 엔드포인트: 사용자 프로젝트 SD targets + 자격증명을 담은 zip 생성
- [ ] 사용자가 임의 VM에 `docker compose up`으로 띄움 — 인스턴스 자체 리소스를 사용
- [ ] 프론트는 사용자가 입력한 Grafana URL만 보관 (관리/설치는 사용자 책임)

#### 비교 의사결정 포인트

- 멀티테넌시 격리 강도 (옵션 A의 라벨 분리로 충분한지 vs 완전 분리 필요한지)
- 운영 인력/비용 (단일 vs N개 스택)
- 사용자 자유도 요구 (대시보드 커스터마이즈 빈도)

### 12.4 Grafana 대시보드 + 프로젝트별 가시화

Option A 채택 시 본 절 진행. Option B 채택 시 사용자가 자체 구성하므로 본 절은 템플릿 제공으로 한정.

- [x] `monitoring/grafana/provisioning/dashboards/` — node/rabbitmq/mysqld/memcached/etcd 5종 대시보드 JSON + provider yaml 프로비저닝
- [ ] Grafana org/folder 자동 생성 — 프로젝트별 folder, datasource label filter `project_id="<keystone_project_id>"`
- [x] `frontend/src/lib/components/monitoring/GrafanaEmbed.svelte` — Grafana iframe 임베드 컴포넌트 (JWT + 빈 상태 폴백)
- [x] `frontend/src/lib/stores/grafana.ts` — Grafana JWT + 대시보드 매핑 캐시 store
- [x] `backend/app/api/common/grafana_auth.py` (신규) — Grafana 임베드용 JWT 발급 엔드포인트 (POST /api/grafana/token, HS256 JWT, standard library만 사용)
- [x] `backend/app/api/common/grafana_auth.py` — GET /api/grafana/dashboards 엔드포인트 + admin role JWT 분기
- [x] `backend/tests/test_grafana_auth.py` — 토큰 발급/클레임 검증/시크릿 미설정 503 + admin role 테스트
- [x] `backend/tests/test_grafana_dashboards.py` — dashboards 엔드포인트 4건 신규
- [x] `/admin/monitoring` 인프라 탭 — 5종 exporter GrafanaEmbed (node/rabbitmq/mysqld/memcached/etcd)
- [x] `/admin/hypervisors` 하단 node_exporter 메트릭 위젯
- [x] `/admin/database-instances` 하단 mysqld 메트릭 위젯
- [x] `/admin/messaging/rabbitmq`, `/admin/messaging/memcached`, `/admin/coordination/etcd` 신규 관리자 페이지
- [x] AdminSidebar "인프라 서비스" 섹션 추가 (RabbitMQ/Memcached/etcd nav)
- [x] `monitoring/grafana/provisioning/dashboards/instance-cpu.json` — CPU 전용 per-instance 대시보드 (`afterglow-instance-cpu`, CPU/메모리/네트워크/디스크 4패널)
- [x] `monitoring/grafana/provisioning/dashboards/instance-gpu.json` — GPU per-instance 대시보드 (`afterglow-instance-gpu`, CPU/메모리/네트워크/디스크 + GPU 6패널)
- [x] `frontend/src/lib/components/instance/MetricsPanel.svelte` — 차트/Grafana 탭 추가 (`isGpu`에 따라 `instance-gpu` / `instance-cpu` 대시보드 자동 선택)
- [x] `backend/app/api/common/grafana_auth.py` / `config.py` / `generate_k8s.py` / `config.toml.example` — `instance-cpu` / `instance-gpu` 대시보드 UID 설정 연동

### 12.5 Open Questions (사용자 확인 필요)

1. **Kolla Ansible 환경의 Prometheus/Grafana**: 운영 OpenStack(Kolla)에 이미 `prometheus`/`grafana` 컨테이너가 떠 있는가? 있다면 그 인스턴스를 재사용할지(scrape job만 추가), 본 저장소의 `deploy/k8s-template/monitoring/`을 분리 운영할지?
2. **`monitoring_scrape_cidr` 결정**: 스크래퍼가 실제로 어느 네트워크에서 도달하는가? (control plane management network / provider network / floating IP 경유?)
3. **VM에서 Prometheus 도달성**: 사용자 VM은 보통 floating IP 없이 fixed IP만 가짐. Prometheus 스크래퍼가 VM의 fixed IP에 직접 접근 가능한 위치에 떠 있는가, 아니면 floating IP가 필수인가?
4. **인증 모델**: Grafana org를 keystone project별로 1:1 매핑할지, 단일 org + folder + label filter로 격리할지?
5. **옵션 A vs B 결정**: 본 결정이 12.3/12.4 작업량을 크게 좌우. 사용자 격리 정책 + 운영 인력 기준 판단 필요.

---

