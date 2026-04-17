# Union 프로젝트 문서

## 개요

Union은 OpenStack 기반 VM 배포 + OverlayFS 마운트 웹 플랫폼입니다. FastAPI 백엔드, SvelteKit 프론트엔드, Redis 캐시로 구성됩니다.

## 기술 스택

- **Frontend**: SvelteKit + TypeScript
- **Backend**: FastAPI (Python 3.12+) + openstacksdk
- **OpenStack**: Nova, Cinder(Ceph), Manila(CephFS + NFS), Keystone
- **Cache**: Redis

---

## 프로젝트 구조

```
afterglow/
├── frontend/                          # SvelteKit 앱
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte           # 로그인
│   │   │   ├── dashboard/             # 대시보드, 인스턴스, 볼륨, 네트워크, 파일 스토리지
│   │   │   ├── create/+page.svelte    # VM 생성 wizard
│   │   │   └── admin/                 # 관리자 페이지
│   │   └── lib/
│   │       ├── components/            # UI 컴포넌트
│   │       ├── stores/               # Svelte stores (auth, sidebar)
│   │       ├── api/client.ts         # Backend API client
│   │       ├── types/resources.ts    # 공통 타입 정의
│   │       └── config/site.ts        # 사이트 설정
│   └── package.json
├── backend/                           # FastAPI 앱
│   ├── app/
│   │   ├── main.py                   # FastAPI 앱, 라우터 등록
│   │   ├── config.py                 # config.toml + 환경변수 로드
│   │   ├── rate_limit.py             # slowapi 설정
│   │   ├── api/
│   │   │   ├── deps.py               # 인증 Depends 함수
│   │   │   ├── compute/              # instances, keypairs, images, flavors
│   │   │   ├── storage/              # volumes, volume_backups, volume_snapshots, file_storage, share_networks, share_snapshots, security_services
│   │   │   ├── network/              # networks, routers, security_groups, loadbalancers
│   │   │   ├── identity/             # auth, admin, admin_flavors, admin_identity, admin_images, admin_gpu, admin_services, admin_notion, profile
│   │   │   ├── container/            # clusters (Magnum), containers (Zun)
│   │   │   ├── k3s/                  # clusters (CRUD+SSE+스케일+삭제), callback (cloud-init 콜백), health (헬스체크)
│   │   │   └── common/               # dashboard, user_dashboard, metrics, libraries, site
│   │   ├── services/
│   │   │   ├── keystone.py           # 토큰 검증, Connection 생성, is_system_admin 판별
│   │   │   ├── nova.py               # Nova 서비스 래퍼
│   │   │   ├── cinder.py             # Cinder 볼륨 관리 + Transfer API
│   │   │   ├── manila.py             # Manila share 관리 (CephFS + NFS, httpx 직접 호출)
│   │   │   ├── glance.py             # Glance 이미지 (배포판 자동 감지)
│   │   │   ├── octavia.py            # Octavia 로드밸런서 관리
│   │   │   ├── neutron.py            # Neutron 네트워크 관리
│   │   │   ├── cloudinit.py          # cloud-init userdata 생성 엔진 (OverlayFS + NFS/CephFS)
│   │   │   ├── libraries.py          # 사전 빌드 라이브러리 카탈로그
│   │   │   ├── library_builder.py    # 자동 라이브러리 빌드 (Manila share + cloud-init VM)
│   │   │   ├── cache.py              # Redis 캐시 (4-tier TTL)
│   │   │   ├── timeseries.py         # Redis 시계열 스냅샷 (10분 주기)
│   │   │   ├── notion_sync.py        # Notion API 동기화 (다중 타겟, SHA256 dedup)
│   │   │   ├── gitlab_oidc.py        # GitLab OIDC 인증
│   │   │   ├── k3s_cluster.py        # K3s 클러스터 관리 (Redis 기반, 레거시)
│   │   │   ├── k3s_db.py             # K3s 클러스터 DB CRUD (MariaDB + Redis fallback, soft-delete)
│   │   │   ├── k3s_cloudinit.py      # K3s cloud-init 렌더링 (서버/에이전트 + OCCM 분기)
│   │   │   ├── k3s_crypto.py         # AES-256-GCM kubeconfig/API키 암호화
│   │   │   ├── k3s_health.py         # K3s 클러스터 노드 헬스 체크 (Kubernetes API 직접 호출)
│   │   │   └── k3s_occm.py           # OCCM cloud.conf + DaemonSet 매니페스트 생성
│   │   ├── models/
│   │   │   ├── storage.py            # 스토리지 관련 Pydantic 모델
│   │   │   ├── compute.py            # 컴퓨트 관련 모델
│   │   │   ├── auth.py               # 인증 모델 (is_system_admin 포함)
│   │   │   ├── containers.py         # Magnum/Zun 컨테이너 모델
│   │   │   ├── k3s.py                # K3s 클러스터 모델
│   │   │   ├── k3s_health.py         # K3s 헬스 모델
│   │   │   ├── progress.py           # SSE 진행률 모델
│   │   │   └── db.py                 # SQLAlchemy ORM (K3sCluster, K3sAgentVM, NotionTarget, NotionConfig)
│   │   ├── templates/
│   │   │   ├── cloudinit_base.yaml.j2  # cloud-init YAML 템플릿
│   │   │   ├── overlay_setup.sh.j2     # OverlayFS 설정 스크립트
│   │   │   ├── strategy_dynamic.sh.j2  # 동적 라이브러리 설치 스크립트
│   │   │   ├── k3s_server.yaml.j2 / k3s_server_occm.yaml.j2   # K3s 서버 cloud-init
│   │   │   ├── k3s_agent.yaml.j2 / k3s_agent_occm.yaml.j2     # K3s 에이전트 cloud-init
│   │   │   └── occm/                   # OCCM cloud_config.conf.j2 + manifests.yaml.j2
│   │   ├── worker.py                   # 독립 실행 K3s 헬스체크 워커 (3분 주기)
│   │   └── database.py                 # SQLAlchemy 비동기 엔진 + 자동 마이그레이션
│   └── pyproject.toml
├── scripts/
│   ├── build_library_shares.py         # 사전 빌드 share 생성 CLI (--proto NFS 지원)
│   ├── sync-version.js                 # 버전 동기화 (루트 → frontend/backend)
│   └── check-version-sync.js           # CI 버전 일치 검증
├── config.toml.example               # 설정 파일 템플릿
├── docker-compose.yml                # 기본 compose (Redis, Backend, Frontend + 선택적 HAProxy, 모니터링)
├── docker-compose.override.yml       # 개발 환경 오버라이드 (볼륨 마운트 + reload)
├── docker-compose.prod.yml           # 프로덕션 환경
├── Dockerfile                        # 멀티스테이지 빌드 (backend, backend-dev, frontend, frontend-dev)
├── deploy/k8s/                       # Kustomize 기반 K8s 배포 (base + overlays/dev + overlays/prod)
├── argocd/                           # ArgoCD Application + AppProject 설정
├── haproxy/                          # HAProxy SSL 터미네이션 설정
├── monitoring/                       # Prometheus + Grafana 설정
└── milestone.md                      # 개발 마일스톤
```

---

## 핵심 아키텍처

### 1. OverlayFS 마운트 구조 (`/opt/layers/`)

```
/opt/layers/
├── lower/                    # 읽기 전용 레이어 (NFS/CephFS 마운트)
│   ├── python311/            # Python 3.11 레이어
│   ├── torch/                # PyTorch 레이어
│   ├── vllm/                 # vLLM 레이어
│   └── jupyter/              # Jupyter 레이어
├── upper/                    # 쓰기 가능 레이어 (Cinder 볼륨)
├── work/                     # OverlayFS workdir
└── merged/                   # OverlayFS 병합 마운트 포인트
```

### 2. 프로토콜 지원 (CephFS + NFS)

- **CephFS**: `access_type="cephx"`, CephX 키링 기반 인증
- **NFS**: `access_type="ip"`, IP/CIDR 기반 접근 제어
- cloud-init 템플릿에서 `share_proto` 필드로 자동 분기

### 3. VM 생성 오케스트레이션

```
POST /api/instances 호출 시 순서:
1. Manila access rule 생성 (NFS: IP 기반 / CephFS: CephX)
2. Cinder 부트 볼륨 생성
3. Cinder upper 볼륨 생성 (OverlayFS upperdir)
4. cloud-init userdata 생성 (프로토콜 자동 감지)
5. Nova 서버 생성 + 볼륨 attach
```

### 4. 요청 흐름

1. 프론트엔드 → `X-Auth-Token` + `X-Project-Id` 헤더로 백엔드 호출
2. `get_os_conn` — Redis 캐시된 Keystone 토큰 검증 → `openstacksdk Connection` 반환
3. Connection 객체에 `conn._afterglow_token`, `conn._afterglow_project_id` 저장

---

## 백엔드 API

### 스토리지

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/file-storage` | 파일 스토리지 목록 |
| POST | `/api/file-storage` | 파일 스토리지 생성 (share_proto: CEPHFS/NFS) |
| GET | `/api/file-storage/{id}` | 파일 스토리지 상세 |
| DELETE | `/api/file-storage/{id}` | 파일 스토리지 삭제 |
| GET | `/api/file-storage/{id}/access-rules` | 접근 규칙 목록 |
| POST | `/api/file-storage/{id}/access-rules` | 접근 규칙 생성 |
| POST | `/api/file-storage/{id}/nfs-access` | NFS 접근 규칙 (멱등) |
| PUT | `/api/file-storage/{id}/visibility` | 공개 범위 설정 |
| GET | `/api/file-storage/{id}/snapshots` | 스냅샷 목록 |
| POST | `/api/file-storage/{id}/snapshots` | 스냅샷 생성 |
| DELETE | `/api/file-storage/snapshots/{id}` | 스냅샷 삭제 |

### 볼륨 Transfer

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/volumes/transfers` | 볼륨 이전 목록 |
| POST | `/api/volumes/{id}/transfer` | 볼륨 이전 생성 |
| POST | `/api/volumes/transfer/{id}/accept` | 볼륨 이전 수락 |
| DELETE | `/api/volumes/transfer/{id}` | 볼륨 이전 취소 |

### 라이브러리

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/libraries` | 라이브러리 카탈로그 (의존성 포함) |
| GET | `/api/libraries/file-storages` | 사전 빌드 파일 스토리지 목록 |

### K3s 클러스터

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/k3s/clusters` | 클러스터 목록 (`?include_deleted=true` 포함) |
| POST | `/api/k3s/clusters` | 클러스터 생성 (SSE 스트리밍) |
| GET | `/api/k3s/clusters/{id}` | 클러스터 상세 |
| DELETE | `/api/k3s/clusters/{id}` | 클러스터 삭제 (soft-delete + Octavia LB 자동 정리) |
| PATCH | `/api/k3s/clusters/{id}/scale` | 에이전트 스케일 조정 |
| GET/HEAD | `/api/k3s/clusters/{id}/kubeconfig` | kubeconfig 다운로드 (AES-256-GCM 복호화) |
| GET | `/api/k3s/health` | 전체 클러스터 헬스 목록 |
| GET | `/api/k3s/clusters/{id}/health` | 클러스터 헬스 상세 |
| POST | `/api/k3s/clusters/{id}/health/check` | 즉시 헬스 체크 트리거 |
| POST | `/api/k3s/callback` | cloud-init 콜백 (일회용 토큰, kubeconfig 수신) |

### 어드민

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/admin/overview` | 관리자 개요 (hypervisor + 서비스 현황) |
| GET | `/api/admin/hypervisors` | 하이퍼바이저 목록 + 디스크/배치 통계 |
| GET | `/api/admin/instances` | 전체 인스턴스 목록 |
| POST | `/api/admin/instances/{id}/migrate` | 라이브/콜드 마이그레이션 |
| GET | `/api/admin/gpu/hosts` | GPU 호스트 현황 (Placement API) |
| GET | `/api/admin/services` | OpenStack 서비스 헬스 전체 |
| GET/PUT | `/api/admin/quotas/{project_id}` | 프로젝트 quota 조회/수정 |
| GET/POST | `/api/admin/notion/targets` | Notion 멀티타겟 CRUD |
| PATCH/DELETE | `/api/admin/notion/targets/{id}` | Notion 타겟 수정/삭제 |
| GET/POST | `/api/admin/k3s/clusters` | K3s 클러스터 어드민 관리 |

---

## K3s 아키텍처

### 생성 흐름

```
POST /api/k3s/clusters (SSE 스트리밍)
1. 보안 그룹 생성 (server + agent 간 내부 통신 허용)
2. 부트 볼륨 생성 (Cinder)
3. cloud-init 렌더링 (OCCM 활성 여부에 따라 k3s_server_occm.yaml.j2 또는 k3s_server.yaml.j2)
4. 서버 VM 생성 (Nova) → k3s 설치 + kubeconfig 생성
5. 서버 VM이 /api/k3s/callback 으로 kubeconfig + node-token 전송
6. 에이전트 VM 병렬 생성 → k3s agent 설치 + 클러스터 조인
```

### 클러스터 삭제 흐름

```
DELETE /api/k3s/clusters/{id}
1. OCCM 활성 시: Octavia LB 조회 (kube_service_{name}_ prefix 매칭) → cascade 삭제
2. 에이전트 VM 병렬 삭제
3. 서버 VM 삭제
4. 보안 그룹 삭제 (3초 대기 후)
5. soft-delete (deleted_at + deleted_by_user_id 기록)
```

### OCCM (OpenStack Cloud Controller Manager)

- `config.toml [k3s] occm_enabled = true` 시 자동 활성화
- cloud-init에서 Kubernetes DaemonSet + RBAC 자동 배포
- `use-octavia=true` 설정으로 Service type=LoadBalancer → Octavia LB 자동 프로비저닝
- 노드 제거 시 OCCM이 자동으로 Kubernetes 노드 객체 + LB pool member 정리
- 클러스터 삭제 시 백엔드가 먼저 Octavia LB를 정리한 뒤 VM 삭제

### 헬스 체크

- `worker.py` 독립 프로세스가 3분 주기로 모든 ACTIVE 클러스터 헬스 프로브
- kubeconfig로 Kubernetes API 직접 호출 → 노드 상태 조회
- 결과를 Redis에 저장 (`afterglow:k3s:health:{cluster_id}`, TTL 10분)
- 프론트엔드에서 5초 간격 자동 갱신 + 즉시 체크 버튼

### 영속성

- 주 저장소: MariaDB (K3sCluster, K3sAgentVM 테이블)
- fallback: Redis (MariaDB 연결 실패 시)
- kubeconfig: AES-256-GCM 암호화 후 저장
- soft-delete: 삭제 시 status='DELETED' + deleted_at 기록 (물리 삭제 없음)

---

## Notion 멀티타겟 동기화

- 복수의 Notion 연동 대상(타겟)을 개별 설정 (각자 API 키, DB ID, 동기화 주기)
- 각 타겟마다 instances / users / hypervisors / GPU spec DB를 별도로 지정
- SHA256 해시 기반 dedup — 내용이 바뀌지 않으면 Notion API 호출 스킵
- 타겟별 API 키는 AES-256-GCM 암호화 후 DB 저장
- `main.py` 백그라운드 루프가 각 타겟의 `interval_minutes` + `last_sync` 기준으로 실행

---

## Docker 개발 환경

### 멀티스테이지 Dockerfile 구조

| 스테이지 | 용도 | 설명 |
|----------|------|------|
| `backend-base` | 공통 | Python 3.12 + uv + 의존성 설치 |
| `backend` | 프로덕션 | uvicorn (no reload, workers=2) |
| `backend-dev` | 개발 | uvicorn --reload, dev 의존성 포함 |
| `frontend-builder` | 빌드 | bun install + build |
| `frontend` | 프로덕션 | node build (SSR) |
| `frontend-dev` | 개발 | bun run dev (Vite HMR) |

### docker-compose 파일 역할

- **docker-compose.yml**: 기본 서비스 정의 (공통)
- **docker-compose.override.yml**: 개발 환경 자동 적용 (볼륨 마운트 + reload)
- **docker-compose.prod.yml**: 프로덕션 배포용

### 개발 환경 실행

```bash
# 개발 모드 (override 자동 병합)
docker compose up

# 프로덕션 모드
docker compose -f docker-compose.prod.yml up -d
```

### 개발 환경 핵심 기능

- **Backend**: 소스코드 볼륨 마운트 (`./backend → /app`) + `uvicorn --reload`로 코드 변경 시 자동 재시작
- **Frontend**: 소스코드 볼륨 마운트 (`./frontend → /app`) + Vite HMR로 브라우저 실시간 갱신
- **익명 볼륨**: `backend-venv`, `frontend-node-modules`, `frontend-svelte-kit`으로 로컬 의존성 충돌 방지
- **DOCKER 환경변수**: `DOCKER=true` 설정 시 Vite가 polling 모드로 파일 변경 감지

---

## 설정

`config.toml` (루트)이 단일 진실 소스. 우선순위: 환경변수 > config.toml > 기본값.

### 주요 설정 항목

| 섹션 | 키 | 설명 | 기본값 |
|------|-----|------|--------|
| `[openstack]` | `manila_share_type` | CephFS용 share type | `cephfs` |
| `[openstack]` | `manila_nfs_share_type` | NFS용 share type | `nfstype` |
| `[openstack]` | `ceph_monitors` | Ceph 모니터 주소 | `""` |
| `[nova]` | `upper_volume_size_gb` | OverlayFS upperdir 볼륨 크기 | `50` |
| `[services]` | `manila` | Manila 서비스 활성화 | `false` |
| `[services]` | `magnum` | Magnum K8s 서비스 활성화 | `false` |
| `[services]` | `zun` | Zun 컨테이너 서비스 활성화 | `false` |
| `[services]` | `k3s` | K3s 클러스터 기능 활성화 | `false` |
| `[k3s]` | `version` | K3s 버전 | `v1.31.4+k3s1` |
| `[k3s]` | `occm_enabled` | OCCM 자동 배포 활성화 | `false` |
| `[k3s]` | `occm_image` | OCCM 컨테이너 이미지 | `registry.k8s.io/...` |
| `[k3s]` | `occm_floating_network_id` | LB용 플로팅 IP 네트워크 ID | `""` |
| `[k3s]` | `callback_base_url` | cloud-init 콜백 수신 URL | - |
| `[database]` | `url` | MariaDB/MySQL 비동기 URL | - |
| `[database]` | `auto_create_tables` | 시작 시 테이블 자동 생성 | `false` |
| `[logging]` | `log_level` | 로그 레벨 | `INFO` |
| `[logging]` | `log_file_path` | 로그 파일 경로 | - |
| `[cache]` | `ttl_fast` | 빠른 캐시 TTL (인스턴스, 볼륨) | `15s` |
| `[cache]` | `ttl_static` | 정적 캐시 TTL (이미지, 플레이버) | `300s` |
| `[session]` | `timeout` | 세션 타임아웃 | `3600s` |
| `[session]` | `absolute_timeout` | 절대 세션 만료 | `14400s` |
| `[gpu]` | `[[gpu.devices]]` | GPU 장치 정의 배열 (vendor_id, device_id, name) | - |

---

## 마일스톤 진행 상태

### 1단계: Manila NFS Share 지원 추가 ✅
- [x] NFS 설정 항목 추가 (`os_manila_nfs_share_type`)
- [x] `FileStorageInfo`에 `nfs_export_location` 필드 추가
- [x] Manila 서비스: NFS access rule, share 공개 설정, snapshot 관리 함수 추가
- [x] cloud-init 템플릿: NFS/CephFS 자동 감지 마운트 지원
- [x] OverlayFS 구조: `/opt/layers/{lower,upper,work,merged}` 단일 마운트 재설계
- [x] 환경변수 등록: `/etc/profile.d/union-env.sh` (PATH, PYTHONPATH, LD_LIBRARY_PATH)
- [x] 인스턴스 생성: NFS 프로토콜 자동 분기 처리

### 2단계: OverlayFS 재설계 ✅
- [x] `/usr/local` + `/opt` 이중 마운트 → `/opt/layers/merged/` 단일 마운트
- [x] NFS 재시도 로직 (30회, 5초 간격)
- [x] systemd 유닛: `After=network-online.target remote-fs.target`
- [x] Cinder upperdir: ext4 자동 포맷 + 마운트

### 3단계: 사전 패키지 관리 시스템 (부분 구현)
- [x] `LibraryConfig`에 `share_proto`, `ubuntu_versions` 필드 추가
- [x] `build_library_shares.py`에 `--proto NFS` 옵션 추가
- [x] 의존성 메타데이터 `union_depends_on` 기록
- [ ] Admin 라이브러리 빌드 API (POST /api/admin/libraries/build)
- [ ] 크로스 프로젝트 접근 자동화 (네트워크 CIDR 기반)
- [ ] 의존성 검증 로직

### 4단계: Cinder 볼륨 마이그레이션 ✅
- [x] Transfer API 서비스 함수 (create/accept/list/delete)
- [x] REST API 엔드포인트

### 5단계: Frontend UI (미구현)
- [ ] 파일 스토리지 프로토콜 선택 UI
- [ ] NFS access rule 관리 UI
- [ ] Admin 라이브러리 카탈로그 관리
- [ ] 볼륨 마이그레이션 UI

### 6단계: 운영 기능 (부분 구현)
- [x] Manila share snapshot 관리 API
- [x] NFS access rule 멱등 생성 (`ensure_nfs_access_rule`)
- [ ] VM 헬스체크 스크립트
- [ ] 볼륨 백업 스케줄링
- [ ] 보안 강화 (NFS root_squash 검증)
- [ ] 로깅/감사 시스템

### 7단계: K3s 클러스터 관리 ✅
- [x] K3s 클러스터 CRUD (SSE 생성 스트리밍, 스케일, soft-delete)
- [x] OCCM 자동 배포 (cloud-init DaemonSet + RBAC)
- [x] Octavia LB 자동 정리 (클러스터 삭제 시 `kube_service_{name}_` prefix 매칭)
- [x] kubeconfig AES-256-GCM 암호화 저장 + HEAD/GET 엔드포인트
- [x] K3s 클러스터 노드 헬스 대시보드 (worker 3분 주기 + 프론트엔드 표시)
- [x] 삭제된 클러스터 이력 조회 (`include_deleted` 파라미터)
- [x] 스케일 업 OCCM 버그 수정 (`occm_enabled` 파라미터 누락)