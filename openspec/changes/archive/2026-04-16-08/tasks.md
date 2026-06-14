## 8. 버그 수정 및 기능 개선 (2026-04-16)

### 8.1 GitHub Actions CI/CD 수정

- [x] `backend/app/utils/version.py` — ruff 포맷 수정 (docstring 후 빈 줄 추가)
- [x] `backend/app/api/container/containers.py` — ruff format 자동 적용 (함수 시그니처 인라인화 등)
- [x] `.github/workflows/docker-build.yml` — macOS arm64 러너 keychain 오류 해결: `Pre-auth registry into config.json` 스텝 (base64 auth 직접 기록) 추가, `Set up Docker Buildx` arm64 는 `driver: docker` 사용, arm64 는 `docker/login-action` 미사용

### 8.2 관리자 이미지 검색 substring 매칭 수정

**문제**: 관리자 전체 이미지 페이지에서 이름 일부 입력 시 검색이 동작하지 않음 (Glance `name=` 필터가 정확 매칭이어서 부분 일치 불가).

- [x] `backend/app/api/identity/admin_images.py` — `_serialize_image()` 헬퍼 분리, `_list_search()` 함수 추가 (전체 이미지 fetch 후 case-insensitive substring 클라이언트 필터 + marker 기반 수동 페이지네이션)
- [x] `backend/tests/test_admin_images.py` — substring 검색 테스트 4개 추가:
  - `test_list_admin_images_search_substring_case_insensitive` — "u" 가 ubuntu/Windows-Update 모두 매칭
  - `test_list_admin_images_search_no_match` — 빈 결과 확인
  - `test_list_admin_images_search_pagination_with_marker` — limit=2 marker 기반 페이지네이션
  - `test_list_admin_images_search_does_not_pass_name_to_glance` — Glance 호출에 `name=` 인자 미전달 검증

### 8.3 시계열 차트 범위 버튼 데이터 이슈 수정

**문제**: 1d/2d/7d/30d 버튼을 눌러도 모두 같은 데이터로 보임. 원인: Redis 컨테이너에 볼륨이 없어 재시작 시 데이터 전부 소실, 그리고 스냅샷 주기가 1시간이어서 1일치 기준 포인트가 24개 불과.

- [x] `docker-compose.yml` — redis 서비스에 `redis-data` 볼륨 마운트 + `--appendonly yes` AOF 활성화
- [x] `backend/app/main.py::_snapshot_loop` — 스냅샷 주기 3600s(1시간) → 600s(10분)으로 단축

### 8.4 관리자 개요 프로젝트 클릭 → quota 슬라이드 패널

- [x] `frontend/src/lib/components/ProjectQuotaPanel.svelte` — 신규 컴포넌트. `GET /api/admin/quotas/{project_id}` 로 현재값+사용량 로드, instances/cores/ram/volumes/gigabytes 편집 폼, `PUT /api/admin/quotas/{project_id}` 로 저장
- [x] `frontend/src/routes/admin/+page.svelte` — ProjectQuotaPanel import, `selectedProject` 상태 추가, 프로젝트 테이블 행에 `onclick`/`onkeydown` 클릭 핸들러 추가, `loadProjectUsage()` 함수 분리, 페이지 하단에 슬라이드 패널 렌더링

### 8.5 k3s 클러스터 soft-delete (삭제 이력 영구 유지)

**문제**: 클러스터 삭제 시 DB에서 물리 삭제되어 이력 조회 불가.

- [x] `backend/app/models/db.py::K3sCluster` — `deleted_at`, `deleted_by_user_id`, `deleted_reason` 컬럼 추가
- [x] `backend/app/models/k3s.py::K3sClusterInfo` — `deleted_at/deleted_by_user_id/deleted_reason` 필드 추가
- [x] `backend/app/database.py::create_tables` — 기존 테이블에 `ALTER TABLE ADD COLUMN IF NOT EXISTS` 마이그레이션 추가
- [x] `backend/app/services/k3s_db.py` — `delete_cluster_record` soft-delete(UPDATE status='DELETED' + deleted_at)로 전환, `list_clusters`/`list_all_clusters` 에 `include_deleted` 파라미터 추가, `_cluster_to_dict` 신규 필드 직렬화
- [x] `backend/app/api/k3s/clusters.py` — `list_k3s_clusters` 에 `?include_deleted=true` 쿼리 파라미터, `delete_k3s_cluster` 에 `user_id` 추출 + soft-delete 호출 + 멱등 처리
- [x] `frontend/src/routes/dashboard/containers/k3s/+page.svelte` — `showDeleted` 토글 버튼 추가, 삭제된 클러스터 회색+취소선+삭제 시각 표시, 삭제된 행에서 액션 버튼 숨김

### 8.6 Notion 다중 DB 동기화 + 중복 갱신 방지 (dedup)

**문제**: 하나의 Notion DB만 설정 가능하고, 매 주기마다 변경 없이도 PATCH를 전송.

- [x] `backend/app/models/db.py::NotionTarget` — 다중 연동 대상 ORM 모델 추가 (`label`, `api_key_encrypted`, `database_id`, `users/hypervisors/gpu_spec _database_id`, `enabled`, `interval_minutes`, `last_sync` 등)
- [x] `backend/app/services/notion_sync.py` — `_parse_dt` 모듈 함수 추출, `sync_to_notion._upsert` 에 SHA256 dedup 추가 (hash 캐시 Redis key: `afterglow:notion:hash:{db_id}:{match_key}`, TTL 24h), `_target_to_dict`/`list_notion_targets`/`get_notion_target`/`create_notion_target`/`update_notion_target`/`delete_notion_target` CRUD 함수 추가
- [x] `backend/app/api/identity/admin_notion.py` — `NotionTargetCreateRequest`/`NotionTargetUpdateRequest` 모델 추가, `GET/POST /notion/targets`, `PATCH/DELETE /notion/targets/{id}`, `POST /notion/targets/{id}/test` 엔드포인트 추가 (기존 `/notion/config` 레거시 유지)
- [x] `backend/app/main.py` — `_run_notion_target_sync()` 헬퍼 추출, `_notion_sync_loop` — `NotionTarget` 다중 대상 우선 처리 (enabled + interval 체크), 없으면 `NotionConfig` fallback
- [x] `frontend/src/routes/admin/notion/+page.svelte` — 단수 폼 → 타겟 카드 리스트 UI로 재작성. "연결 추가" 버튼, 카드별 enabled 상태/마지막 동기화/인라인 수정 폼/지금 동기화/삭제 버튼
- [x] `backend/tests/test_notion.py` — dedup skip/patch/신규 POST 3건 + 다중 타겟 CRUD API 6건 테스트 추가 (총 9건)

### 8.6.1 Notion 주기 자동 동기화 워커 구동 + 기본 간격 30분 + 경량 이미지 분리

**배경**: `notion_worker.py`가 구현되어 있었으나 어디에서도 실행되지 않는 고아 모듈이었음(`main.py` startup 미등록). 또한 워커가 backend 이미지(OpenTofu ~80MB 포함)를 그대로 사용해 낭비.

- [x] `backend/app/models/db.py`, `admin_notion.py`, `notion_sync.py`, `migrations/002…` — `interval_minutes` 기본값 5→30
- [x] `frontend/src/lib/components/admin/notion/NotionTargetAddForm.svelte`, `NotionTargetEditForm.svelte` — 폼 기본값 5→30
- [x] `backend/migrations/015_notion_interval_default_30.sql` — 기존 타겟/설정 5→30 마이그레이션 SQL
- [x] `backend/app/services/gpu_inventory.py` (신규) — `VENDOR_MAP`, `PCI_DEVICE_MAP`, `_collect_gpu_hosts`, `get_gpu_spec_list`, `build_alias_to_device_name_map` 등을 FastAPI 의존 없는 서비스 모듈로 추출
- [x] `backend/app/services/openstack_inventory.py` (신규) — `collect_instance_data`, `collect_hypervisor_data`, `_fetch_hypervisors_raw`를 FastAPI 의존 없는 서비스 모듈로 추출
- [x] `backend/app/services/k3s_errors.py` (신규) + `k3s_kube.py` — `HTTPException` → `K3sApiError` 치환으로 drover FastAPI 차단점 제거
- [x] `backend/app/main.py` — `K3sApiError` exception handler 등록
- [x] `backend/app/notion_worker.py` — import 경로를 `admin_*` 라우터 → `gpu_inventory`/`openstack_inventory` 서비스 모듈로 교체 (FastAPI-free)
- [x] `backend/pyproject.toml` — `[dependency-groups] worker` 추가 (fastapi/uvicorn/boto3/asyncssh 등 API 전용 패키지 제외)
- [x] `Dockerfile` — `worker-builder` + `worker` 스테이지 추가 (OpenTofu/curl/unzip 제외, 워커 의존성 그룹만 설치)
- [x] `.github/workflows/docker-build.yml` — `worker` 타겟 빌드/푸시 → `afterglow-worker` 이미지로 CI 등록
- [x] `docker-compose.yml`, `docker-compose.prod.yml` — drover 이미지 `afterglow-api` → `afterglow-worker`, `notion-worker` 서비스 추가
- [x] `deploy/k8s-template/base/worker/` — `deployment.yaml` 이미지 교체, `notion-deployment.yaml` 신규, `kustomization.yaml` 등록
- [x] `deploy/kolla/ansible/roles/afterglow/` — `afterglow_drover_image` 변수 추가, worker 이미지 교체, `afterglow-notion-worker` 컨테이너 추가
- [x] `backend/tests/test_notion_worker.py` (신규) — 기본값 30 검증 2건, 워커 사이클 interval 존중 5건, FastAPI-free 회귀 가드 1건

### 8.7 인스턴스 로그 전체 조회 + HEAD kubeconfig + K3s 헬스 대시보드

- [x] `backend/app/api/compute/instances.py` — 콘솔 로그 `length` 파라미터 `ge=1` → `ge=0` 변경 (Nova API에서 `length=0`은 전체 로그)
- [x] `backend/tests/test_instances.py` — `length=0` 전체 로그 테스트, 음수 `length` 422 테스트 추가
- [x] `backend/app/api/k3s/clusters.py` — kubeconfig 엔드포인트를 `@router.api_route(methods=["GET","HEAD"])`로 변경 (프론트 HEAD 요청 405 해결)
- [x] `backend/tests/test_k3s_clusters.py` — HEAD kubeconfig 준비/미준비 테스트 추가
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — 헬스 대시보드 연동 (K3sClusterHealth/K3sNodeHealth 인터페이스, 상태 배지, 노드별 ready 상태 + role + kubelet 버전, 즉시 체크 버튼)

### 8.8 K3s 클러스터 삭제 시 Octavia LB 자동 정리 + OCCM 스케일 업 버그 수정

**문제**: OCCM 활성 클러스터 삭제 시 Kubernetes LoadBalancer 서비스가 생성한 Octavia LB가 orphan됨. 또한 스케일 업 시 추가된 에이전트에 `cloud-provider=external` 플래그 미전달.

- [x] `backend/app/api/k3s/clusters.py` — `delete_k3s_cluster()`: VM 삭제 전 OCCM LB 자동 정리 추가. `octavia.list_load_balancers()` 로 전체 LB 조회 후 `kube_service_{cluster_name}_` prefix 매칭하여 `cascade=True` 삭제. 실패 시 warning 로그 후 삭제 계속 진행 (best-effort)
- [x] `backend/app/api/k3s/clusters.py` — `_scale_agents()` 스케일 업: `generate_agent_userdata()` 호출 시 `occm_enabled=bool(cluster.get("occm_enabled"))` 누락 파라미터 추가 (기존 에이전트와 동일한 OCCM 설정 적용)
- [x] `backend/tests/test_k3s_clusters.py` — LB 정리 테스트 3건 추가: OCCM LB prefix 매칭 삭제 확인, LB 정리 실패 시 삭제 계속, OCCM 비활성 시 LB 조회 스킵

### 8.9 K3s 스케일 다운 시 K8s 노드 강제 삭제 + 헬스체크 프론트엔드 버그 수정

**문제 1**: 스케일 다운 시 VM을 삭제해도 K8s 노드는 NotReady 상태로 잔존. OCCM `node_lifecycle_controller`가 삭제된 OpenStack 인스턴스를 조회 시 `failed to find object` 에러를 무한 반복.

**문제 2**: `K3sClusterDetailPanel`의 Svelte `$effect` 리액티비티 버그로 5초 폴링 시마다 health 2회 + kubeconfig HEAD 1회 = 4 요청/5초 발생.

- [x] `backend/app/services/k3s_kube.py` — **신규** K8s API 직접 호출 유틸리티. kubeconfig에서 client cert/key 추출 + mTLS로 `DELETE /api/v1/nodes/{name}` 호출. 200/404 = True, 그 외 = False (best-effort, 예외 전파 안 함)
- [x] `backend/app/services/k3s_db.py` — `get_agent_vm_names(cluster_id, vm_ids)` 추가: `K3sAgentVM` 테이블에서 vm_id → name 매핑 반환
- [x] `backend/app/api/k3s/clusters.py` — `_scale_agents()` 스케일 다운: VM 삭제 전 `k3s_kube.delete_k8s_nodes()`로 K8s 노드 먼저 삭제 (best-effort)
- [x] `backend/app/api/k3s/clusters.py` — `delete_k3s_cluster()`: LB 정리 후, VM 삭제 전에 모든 K8s 노드 (에이전트 + 서버) 삭제 (best-effort)
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — `initialCheckDone` 플래그 추가. Effect 2가 `cluster?.status === 'ACTIVE'` 진입 시 1회만 실행되도록 수정. 요청 4회/5초 → 2회/5초로 감소
- [x] `backend/tests/test_k3s_kube.py` — **신규** 유닛 테스트 7건: 성공/404/500/연결오류/kubeconfig없음/다중노드/실패시계속진행
- [x] `backend/tests/test_k3s_clusters.py` — K8s 노드 삭제 테스트 3건 추가: 클러스터 삭제 시 노드 정리, K8s 오류 시 VM 삭제 계속 진행

### 8.10 Cloud Provider OpenStack 전체 플러그인 통합

플러그인 레지스트리 패턴 도입 — OCCM 포함 6개 플러그인 전체 구현.
`backend/app/services/k3s_plugins/` 패키지로 통합 관리.

- [x] **플러그인 프레임워크** (`k3s_plugins/` 패키지): Protocol 정의, 레지스트리 집계 함수, 통합 cloud-init 템플릿 (기존 4개 → 2개로 통합)
- [x] **OCCM 이전**: `k3s_plugins/occm.py`로 로직 이전, `k3s_occm.py` 위임 래퍼로 유지 (하위호환)
- [x] **Cinder CSI**: K8s PVC → Cinder 블록 스토리지 자동 프로비저닝. `k3s_plugins/cinder_csi.py` + `templates/k3s_plugins/cinder_csi/manifests.yaml.j2`
- [x] **Manila CSI**: ReadWriteMany PVC → Manila NFS share. NFS CSI 드라이버 포함 배포. Union OverlayFS 시너지
- [x] **Octavia Ingress Controller**: K3s Traefik과 공존, `ingressClassName: openstack`으로 분리. **Per-project 관리 사용자 + Application Credential** 모델로 인증 일원화. subnet 클러스터 네트워크에서 자동 도출. 삭제 시 `kube_ingress_*` LB 자동 정리 + App Cred 회수.
- [x] **Keystone Webhook Auth**: TLS self-signed 인증서 생성 + K3s API 서버 webhook 설정. `cryptography` 라이브러리 사용
- [x] **Barbican KMS**: K8s Secret at-rest 암호화. `--encryption-provider-config` API 서버 인자 + Unix socket DaemonSet
- [x] DB 마이그레이션: `plugins_enabled JSON` 컬럼 추가 (`004_k3s_plugins.sql`)
- [x] 콜백 확장: `plugin_status: dict[str, str]` 필드로 플러그인별 배포 결과 보고
- [x] 테스트: `test_k3s_plugins.py` 41개 (435 passed, 1 xfailed)

config.toml 신규 섹션: `[k3s]` 하위 `cinder_csi_*`, `manila_csi_*`, `keystone_auth_*`, `octavia_ingress_*`, `barbican_kms_*`

### 8.11 네트워크 UX 개선 + 볼륨 강제삭제 + K3s DB 수정

- [x] **K3s DB 수정**: `database.py`의 `create_tables()`에 `plugins_enabled JSON` ALTER TABLE 추가 — 컨테이너 재시작만으로 자동 적용
- [x] **서브넷 편집 기능**: 네트워크 상세 페이지에서 서브넷 이름/게이트웨이/DHCP 인라인 편집 (`PUT /api/networks/subnets/{id}`)
- [x] **포트 페이지 제거**: 사용자 불필요. 사이드바에서 제거, 페이지 삭제
- [x] **Floating IP 자동 관리**: 사이드바에서 Floating IP 페이지 제거. 인스턴스 상세 패널에서 원클릭 요청/해제+삭제(`POST/DELETE /api/instances/{id}/floating-ip`). 인스턴스 삭제 시 FIP 자동 정리
- [x] **볼륨 강제 삭제**: `error`/`error_deleting` 상태 볼륨을 관리자가 강제 삭제 (`POST /api/volumes/{id}/force-delete`, Cinder `os-reset_status` + `os-force_delete`)

### 8.12 K3s API LB — LB-first 전략 + Provider 직접 VIP

**문제**: 기존 방식은 VM 생성 후 콜백 시점에 LB를 완전히 구성해야 해서 서버 VM이 LB 없이 떠있는 시간이 존재했고, FIP를 통해 외부 노출해야 했다.

- [x] `backend/app/services/octavia.py` — `create_load_balancer()` 에 `vip_network_id` 파라미터 추가 (provider 네트워크에 VIP 직접 생성)
- [x] `backend/app/api/k3s/clusters.py` — LB-first 전략: VM 생성 전에 LB(ACTIVE 대기) → listener(TCP:6443) → pool(ROUND_ROBIN) 순서로 완전 구성. LB VIP를 k3s TLS SAN으로 사용. `api_lb_pool_id` DB에 저장
- [x] `backend/app/api/k3s/callback.py` — `_finalize_api_lb()` 간소화: listener/pool 생성 로직 제거 (clusters.py로 이동), member 추가 + health monitor만 담당
- [x] `backend/app/models/db.py` — `K3sCluster` 에 `api_lb_pool_id`, `api_fip_id`, `api_fip_address`, `api_lb_id` 컬럼 추가
- [x] `backend/app/database.py` — 관련 ALTER TABLE 마이그레이션 추가
- [x] `backend/app/config.py` — `k3s_api_lb_vip_network_id` 설정 추가 (provider 네트워크 ID, 설정 시 FIP 없이 VIP 직접 생성)
- [x] `backend/app/services/k3s_db.py` — `api_lb_pool_id` 필드 직렬화/역직렬화 추가
- [x] 하위호환: `k3s_api_lb_vip_network_id` 미설정 시 기존 tenant 서브넷 + FIP 방식 유지

### 8.13 Fedora CoreOS (FCOS) k3s 노드 지원

**목표**: k3s 클러스터 생성 시 `os_type: fcos`를 선택하면 Ubuntu cloud-init 대신 Ignition JSON을 주입하여 FCOS 이미지로 노드를 프로비저닝.

- [x] `backend/app/models/k3s.py` — `CreateK3sClusterRequest` 에 `os_type: str = "ubuntu"` 추가 (validator: `ubuntu` | `fcos`)
- [x] `backend/app/models/db.py` — `K3sCluster` 에 `os_type` 컬럼 추가 (default `ubuntu`)
- [x] `backend/app/database.py` — `ALTER TABLE k3s_clusters ADD COLUMN os_type` 마이그레이션 추가
- [x] `backend/app/services/k3s_cloudinit.py` — 완전 재작성. `UserdataResult(data, config_drive)` NamedTuple 반환. FCOS 경로: Python으로 Ignition JSON 직접 조립 (base64+URL 인코딩), Jinja2는 bash 스크립트 렌더링에만 사용. `INSTALL_K3S_SKIP_SELINUX_RPM=true` 포함
- [x] `backend/app/templates/k3s_server_fcos_callback.sh.j2` — FCOS 서버 콜백 bash 스크립트 템플릿 (신규)
- [x] `backend/app/templates/k3s_agent_fcos_join.sh.j2` — FCOS 에이전트 조인 bash 스크립트 템플릿 (신규)
- [x] `backend/app/api/k3s/clusters.py` — `os_type` 분기: FCOS → `k3s_fcos_image_id`, `config_drive=True`; Ubuntu → 기존 이미지, `config_drive=False`
- [x] `backend/app/api/k3s/callback.py` — `_provision_agents()` 에서 `os_type` 읽어 이미지·userdata 분기
- [x] `backend/app/config.py` — `k3s_fcos_image_id: str = ""` 설정 추가
- [x] `backend/app/services/k3s_db.py` — `os_type` 직렬화 추가
- [x] `backend/tests/test_k3s_fcos.py` — FCOS 전용 테스트 17건 (Ignition JSON 구조, systemd 유닛, 파일 인코딩, os_type 유효성 검증 등)
- [x] 하위호환: `os_type` 미설정 시 기존 Ubuntu cloud-init 동작 완전 유지

config.toml 신규: `[k3s]` 아래 `fcos_image_id = ""`, `api_lb_vip_network_id = ""`

**2026-06-03 FCOS 안정화 (A1, A2, A4)**

- [x] `backend/app/templates/k3s_server_fcos_callback.sh.j2` — Ubuntu 기준으로 drift 수정: `export PATH="/usr/local/bin:$PATH"` 상단 추가, kube-apiserver `/livez` 인증 대기 루프, k3s NRestarts 재시작 루프 감지, 플러그인 apply `--validate=false` + stderr 캡처, plugin_status `{status, error}` 구조 통일, `secret_cloud_config_status` payload 포함, `SERVER_IP` 산출을 `ip route get 8.8.8.8 | awk src`로 변경
- [x] `backend/app/templates/k3s_agent_fcos_join.sh.j2` — `NODE_IP=$(ip route get 8.8.8.8 ... src)` 산출 추가, `INSTALL_K3S_EXEC="agent --node-ip ${NODE_IP} ..."` (agent 서브커맨드 + --node-ip 누락 수정)
- [x] `backend/tests/test_k3s_fcos.py` — `TestFCOSCallbackScript` 클래스 7건(PATH export, /livez, NRestarts, --validate=false+stderr, {status,error}, secret_cloud_config_status, ip route), `TestFCOSAgentNodeIp` 클래스 4건(--node-ip, ip route, agent 서브커맨드, extra_args 보존) 추가 — 총 28건
- [x] `backend/tests/test_k3s_clusters.py` — FCOS 503 가드 2건 추가 (k3s_fcos_image_id 미설정 시 503, ubuntu 요청은 503 미발생)
- **알려진 제약**: 멀티 NIC 환경에서 FCOS는 NetworkManager가 보조 NIC에 default route를 탈취할 수 있음. `--node-ip` 고정으로 노드 등록 IP는 안전하나, 완전한 멀티 NIC 지원(route-metric/ipv4.never-default Ignition 주입)은 별도 PR로 진행 예정

### 8.14 k3s 부팅 데드락 수정 + callback.sh 진단 개선

**문제**: barbican_kms / keystone_auth 플러그인이 부팅 시점 불가능한 의존성을 apiserver에 주입해 control plane이 영구 데드락에 빠짐. kubectl get nodes 시 노드가 보이지 않음.

- [x] `backend/app/services/k3s_plugins/barbican_kms.py` — `should_deploy()` 강제 False (KMS 소켓 chicken-and-egg 데드락 방지, host static pod 재설계 전까지)
- [x] `backend/app/services/k3s_plugins/keystone_auth.py` — `should_deploy()` 강제 False (부팅 직후 webhook service URL resolve 실패 방지)
- [x] `backend/app/templates/k3s_server.yaml.j2` — `set -o pipefail` 추가, apiserver `/livez` readiness 폴링(최대 10분), kubectl `--validate=false`, tee 파이프 제거(>> redirect로 교체)
- [x] `backend/tests/test_k3s_clusters.py` — 플러그인 게이팅 신규 테스트 4건

**향후 작업**:
- [x] Barbican KMS host static pod 재설계 (부팅 전 소켓 준비, apiserver 재시작 트리거) — 20항 참조
- [x] Keystone Auth hostNetwork static pod 재설계 (webhook URL을 127.0.0.1:port로 변경) — 20항 참조
- [x] callback.sh에서 k3s 재시작 루프 감지 시 success=false 보고

### 8.15 k3s 노드 멀티 NIC + DB deleted 인스턴스 필터링 (2026-05-17)

- [x] k3s 노드 멀티 NIC attach/detach API + udev/netplan 자동 적용
- [x] DB 인스턴스 deleted 필터링 (Trove deleted=1 행 제외)

### 8.16 k3s ConfigMap/Secret CRUD 프론트엔드 (2026-05-17)

- [x] `frontend/src/lib/types/resources.ts` — `ConfigMapInfo`, `SecretInfo` 타입 추가
- [x] `frontend/src/lib/api/k3sResources.ts` — namespaces/configmaps/secrets CRUD API 클라이언트
- [x] `frontend/src/lib/stores/k3sClusterDetail.svelte.ts` — namespace/cm/secret 상태 + load/save/delete 메서드 추가
- [x] `frontend/src/lib/components/k3s/K3sNamespaceSelector.svelte` — 네임스페이스 셀렉터
- [x] `frontend/src/lib/components/k3s/K3sResourceEditor.svelte` — key-value 편집 모달
- [x] `frontend/src/lib/components/k3s/K3sSecretValueDisplay.svelte` — base64 디코딩 + Reveal 토글 + 복사
- [x] `frontend/src/lib/components/k3s/K3sClusterConfigMapsCard.svelte` — ConfigMap 목록/생성/편집/삭제
- [x] `frontend/src/lib/components/k3s/K3sClusterSecretsCard.svelte` — Secret 목록/생성/편집/삭제 (type 선택)
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — namespace selector + ConfigMaps/Secrets 카드 통합

### 8.17 k3s ConfigMap/Secret CRUD 백엔드 (2026-05-17)

- [x] `backend/app/services/k3s_kube.py` — `_kube_client` asynccontextmanager (mTLS K8s API 클라이언트), `list_namespaces`, ConfigMap/Secret CRUD (list/get/create/update/delete). Secret 은 함수 내에서 plain text → base64 인코딩 처리
- [x] `backend/app/models/k3s.py` — `ConfigMapInfo`, `ConfigMapCreateRequest`, `ConfigMapWriteRequest`, `SecretInfo`, `SecretCreateRequest`, `SecretWriteRequest` Pydantic 모델 추가
- [x] `backend/app/api/k3s/configmaps.py` — **신규** ConfigMap CRUD 라우터 + namespace 목록 (`/api/k3s/clusters/{id}/namespaces`, `/configmaps`, `/namespaces/{ns}/configmaps/{name}`)
- [x] `backend/app/api/k3s/secrets.py` — **신규** Secret CRUD 라우터 (rec extra 에 data 미포함, 이름/namespace 만)
- [x] `backend/app/api/k3s/__init__.py` — `k3s_configmaps_router`, `k3s_secrets_router` lazy import 추가
- [x] `backend/app/main.py` — 두 라우터 `service_k3s_enabled` 블록에 마운트
- [x] `backend/tests/test_k3s_configmaps.py` — **신규** 8개 테스트 (401/404/list/get/create/update/delete + namespaces)
- [x] `backend/tests/test_k3s_secrets.py` — **신규** 8개 테스트 (401/404/list/get/create/update/delete + plain→service 전달 확인)

### 8.18 k3s Cloud Shell 프론트엔드 (2026-05-17)

- [x] k3s Cloud Shell — 웹 kubectl 터미널 (PVC 영속, user impersonation, idle 15분)
- [x] `frontend/src/lib/types/resources.ts` — `CloudShellTicket` 타입 추가
- [x] `frontend/src/lib/api/k3sResources.ts` — `createShellTicket()` 헬퍼 추가
- [x] `frontend/src/lib/stores/k3sClusterDetail.svelte.ts` — `shellOpen` state + `openShell`/`closeShell` 메서드 + reset 정리
- [x] `frontend/src/lib/components/k3s/K3sCloudShellOverlay.svelte` — **신규** 풀스크린 오버레이, xterm.js + K8s exec WebSocket (v4.channel.k8s.io binary framing, channel 0/1/2/4) + ResizeObserver + idle timeout(4408) UI
- [x] `frontend/src/lib/components/k3s/K3sCloudShellButton.svelte` — **신규** 헤더 진입 버튼 (ACTIVE + kubeconfig 준비 시만 표시)
- [x] `frontend/src/lib/components/k3s/K3sClusterHeader.svelte` — kubeconfig 다운로드 버튼 앞에 Cloud Shell 버튼 추가
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — `shellOpen` 시 overlay 마운트

---

