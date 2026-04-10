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
union/
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
│   │   │   ├── storage/              # volumes, volume_backups, volume_snapshots, file_storage
│   │   │   ├── network/              # networks, routers, security_groups, loadbalancers
│   │   │   ├── identity/             # auth, admin, profile
│   │   │   ├── container/            # clusters (Magnum), containers (Zun)
│   │   │   └── common/               # dashboard, metrics, libraries, site
│   │   ├── services/
│   │   │   ├── keystone.py           # 토큰 검증, Connection 생성
│   │   │   ├── nova.py               # Nova 서비스 래퍼
│   │   │   ├── cinder.py             # Cinder 볼륨 관리 + Transfer API
│   │   │   ├── manila.py             # Manila share 관리 (CephFS + NFS)
│   │   │   ├── cloudinit.py          # cloud-init userdata 생성 엔진
│   │   │   ├── libraries.py          # 사전 빌드 라이브러리 카탈로그
│   │   │   ├── cache.py              # Redis 캐시
│   │   │   └── neutron.py            # Neutron 네트워크 관리
│   │   ├── models/
│   │   │   ├── storage.py            # 스토리지 관련 Pydantic 모델
│   │   │   ├── compute.py            # 컴퓨트 관련 모델
│   │   │   ├── auth.py               # 인증 모델
│   │   │   └── progress.py           # SSE 진행률 모델
│   │   └── templates/
│   │       ├── cloudinit_base.yaml.j2  # cloud-init YAML 템플릿
│   │       ├── overlay_setup.sh.j2      # OverlayFS 설정 스크립트
│   │       └── strategy_dynamic.sh.j2   # 동적 라이브러리 설치 스크립트
│   └── pyproject.toml
├── scripts/
│   └── build_library_shares.py       # 사전 빌드 share 생성 CLI (--proto NFS 지원)
├── config.toml.example               # 설정 파일 템플릿
├── docker-compose.yml                # 기본 compose (공통 서비스)
├── docker-compose.override.yml       # 개발 환경 오버라이드 (실시간 디버깅)
├── docker-compose.prod.yml           # 프로덕션 환경
├── Dockerfile                        # 멀티스테이지 빌드 (backend, backend-dev, frontend, frontend-dev)
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
3. Connection 객체에 `conn._union_token`, `conn._union_project_id` 저장

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