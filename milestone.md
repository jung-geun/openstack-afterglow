# Afterglow 프로젝트 마일스톤

---

## 0. 프로젝트 개요 (구 PLAN.md)

> 이 섹션은 초기 설계 문서(PLAN.md)를 이전한 내용입니다.

## Context

운영 중인 OpenStack 환경(Nova, Cinder/Ceph, Manila/CephFS, Keystone)에서 VM을 배포할 때, 원하는 OS 이미지를 선택하고 필요한 라이브러리(Python, PyTorch, vLLM, Jupyter)를 선택하면 Manila share에 마운트하고 OverlayFS로 합성해서 부팅하는 웹 플랫폼. 두 가지 라이브러리 전략(사전 빌드 공유 share / 동적 생성)을 모두 지원.

## 기술 스택

- **Frontend**: SvelteKit + TypeScript
- **Backend**: FastAPI (Python) + openstacksdk
- **OpenStack**: Nova, Cinder(Ceph), Manila(CephFS), Keystone

---

## 프로젝트 구조

```
afterglow/
├── frontend/                          # SvelteKit 앱
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte           # 로그인
│   │   │   ├── dashboard/+page.svelte # VM 목록
│   │   │   ├── create/+page.svelte    # VM 생성 wizard
│   │   │   └── admin/+page.svelte     # 라이브러리 share 관리
│   │   └── lib/
│   │       ├── components/wizard/     # 단계별 wizard 컴포넌트
│   │       ├── stores/               # Svelte writable stores (auth, wizard)
│   │       └── api/                  # Backend API client
│   ├── package.json
│   └── svelte.config.js
├── backend/                           # FastAPI 앱
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py                  # OpenStack 연결 설정
│   │   ├── api/
│   │   │   ├── auth.py                # Keystone 인증
│   │   │   ├── instances.py           # VM CRUD (핵심 오케스트레이션)
│   │   │   ├── images.py              # OS 이미지 목록
│   │   │   ├── flavors.py             # 플레이버 목록
│   │   │   ├── libraries.py           # 라이브러리 설정
│   │   │   └── admin.py              # share 빌드 관리
│   │   ├── services/
│   │   │   ├── nova.py               # Nova 서비스 래퍼
│   │   │   ├── cinder.py             # Cinder 볼륨 관리
│   │   │   ├── manila.py             # Manila share 관리 (핵심)
│   │   │   └── cloudinit.py          # cloud-init 생성 엔진 (핵심)
│   │   ├── models/                   # Pydantic 모델
│   │   └── templates/
│   │       ├── overlay_setup.sh.j2   # OverlayFS 설정 스크립트 템플릿
│   │       ├── cloudinit_base.yaml.j2
│   │       └── strategy_dynamic.sh.j2
│   ├── requirements.txt
│   └── Dockerfile
├── scripts/
│   └── build_library_shares.py       # 사전 빌드 share 생성 관리자 스크립트
├── docker-compose.yml
└── .env.example
```

---

## 핵심 설계 결정사항

### 1. OverlayFS 마운트 전략

**`/usr/local`과 `/opt`만 오버레이** — `/usr` 전체나 `/`를 오버레이하면 패키지 매니저와 init 시스템이 깨짐. pip 설치 라이브러리는 자연스럽게 `/usr/local`에 위치하므로 이 경로가 최적.

**lowerdir 순서**: `lowerdir=vllm_share:torch_share:python_share:base_lower`
- 왼쪽이 우선순위 높음 (상위 레이어가 하위 레이어보다 우선)
- 의존성 관계에 따라 토폴로지 정렬로 순서 결정

**upperdir = 전용 Cinder 볼륨**: 재부팅/stop-start 후에도 사용자 변경사항 유지.

### 2. 두 가지 라이브러리 전략

#### Strategy A: 사전 빌드 공유 share (read-only, 고성능)

```
Manila Share (read-only, CephFS)
  python3.11/  → 여러 VM이 공유
  torch2.x/    → read-only access rule
  vllm/        →
  jupyter/     →

OverlayFS:
  lowerdir = /mnt/python:base_lower
  upperdir  = /mnt/writable (Cinder volume)
  workdir   = /mnt/work
  merged    = /usr/local (pivot-mount)
```

- 장점: 빠른 부팅, 효율적인 스토리지 (공유)
- `scripts/build_library_shares.py`로 관리자가 사전 구축

#### Strategy B: 동적 생성 (유연성)

```
새 Manila Share (read-write, 이 VM 전용)
  cloud-init 첫 부팅 시 pip install 실행
  OverlayFS upper layer로 사용
```

- 장점: 항상 최신 버전, 커스텀 설정 가능
- 단점: 첫 부팅이 느림 (설치 시간)

### 3. cloud-init 시스템 설계

cloud-init `runcmd`는 최초 1회만 실행 → **systemd 유닛으로 영속화** 필요:

```yaml
# cloud-init이 생성하는 내용:
write_files:
  - path: /etc/ceph/ceph.client.union.keyring  # CephX 인증정보 주입
  - path: /opt/union/overlay_setup.sh          # OverlayFS 설정 스크립트
  - path: /etc/systemd/system/union-overlay.service  # 매 부팅 시 실행

runcmd:
  - systemctl enable union-overlay
  - systemctl start union-overlay
```

**CephFS 마운트 방법**: 커널 드라이버(`mount -t ceph`) 우선, 없으면 `ceph-fuse` 폴백.

Manila가 access rule 생성 시 반환하는 CephX 크리덴셜을 cloud-init에 주입.

### 4. 인스턴스 생성 오케스트레이션 (`instances.py`)

```
POST /api/instances 호출 시 순서:

1. Manila access rule 생성 (Strategy A) 또는 신규 share 생성 (Strategy B)
2. Cinder 부트 볼륨 생성 (선택된 OS 이미지 기반)
3. Cinder 상위 레이어 볼륨 생성 (writable upperdir용)
4. cloud-init userdata 생성 (CephX 크리덴셜, share export location 포함)
5. Nova 서버 생성 (block_device_mapping_v2)

실패 시 역순으로 cleanup:
  → delete nova server → delete cinder volumes → delete/revoke manila
```

---

## Backend API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/auth/login` | Keystone 인증, token 반환 |
| GET | `/api/images` | OS 이미지 목록 (Glance/Cinder) |
| GET | `/api/flavors` | 플레이버 목록 |
| GET | `/api/libraries` | 사용 가능한 라이브러리 설정 목록 |
| GET | `/api/shares` | 사전 빌드된 Manila share 목록 |
| POST | `/api/instances` | VM 생성 (오케스트레이션) |
| GET | `/api/instances` | VM 목록 |
| GET | `/api/instances/{id}` | VM 상세 정보 |
| DELETE | `/api/instances/{id}` | VM 삭제 (share 정리 포함) |
| POST | `/api/admin/shares/build` | 사전 빌드 share 생성/업데이트 |

---

## Frontend Wizard 흐름

```
Step 1: 기본 OS 이미지 선택
  └── Ubuntu 22.04, Rocky Linux 9, ...

Step 2: 플레이버 선택 (CPU/RAM/GPU)

Step 3: 라이브러리 선택 (체크박스)
  ├── Python 3.11
  ├── PyTorch 2.x (requires Python)
  ├── vLLM (requires PyTorch)
  └── Jupyter Lab

Step 4: 마운트 전략 선택
  ├── A: 사전 빌드 공유 share (빠른 부팅, 읽기 전용)
  └── B: 동적 생성 (느린 첫 부팅, 최신 버전)

Step 5: 요약 & 배포
```

---

## 보안 고려사항

- Keystone 토큰은 backend에서만 관리, frontend에는 세션 쿠키로 추상화
- CephX 크리덴셜은 backend에서 cloud-init에 주입, 절대 API 응답에 노출 금지
- Manila share access rule은 VM별 고유 CephX 사용자로 격리
- HTTPS 필수 (CephX 키 전송 보호)

---

## 구현 단계별 계획

### 1단계: 프로젝트 초기 설정

- Backend: FastAPI 프로젝트 구조 생성 (app/, api/, services/, models/, templates/)
- `requirements.txt`: fastapi, uvicorn, openstacksdk, python-keystoneclient, jinja2, pydantic
- `config.py`: OpenStack 연결 설정, 환경변수 관리
- Frontend: SvelteKit + TypeScript 프로젝트 초기화
- `docker-compose.yml`: frontend + backend
- `.env.example`

### 2단계: Backend — Keystone 인증 API

- `POST /api/auth/login`: Keystone 토큰 발급
- `POST /api/auth/logout`: 토큰 폐기
- `GET /api/auth/me`: 현재 사용자 정보
- 미들웨어: 요청마다 Keystone 토큰 유효성 검증
- Pydantic 모델: `LoginRequest`, `TokenResponse`, `UserInfo`

### 3단계: Backend — OpenStack 서비스 래퍼 (Nova, Cinder, Glance)

- `services/nova.py`: 서버 생성/조회/삭제/시작/정지, 콘솔 URL 조회
- `services/cinder.py`: 볼륨 생성(이미지 기반)/삭제/조회
- `GET /api/images`: Glance 이미지 목록 반환
- `GET /api/flavors`: Nova 플레이버 목록 반환
- Pydantic 모델: `ImageInfo`, `FlavorInfo`, `InstanceInfo`

### 4단계: Backend — Manila 서비스 (핵심)

- `services/manila.py` 구현:
  - `create_share()`: CephFS share 생성
  - `delete_share()`: share 삭제
  - `create_access_rule()`: CephX access rule 생성 (read-only / read-write)
  - `revoke_access_rule()`: access rule 삭제
  - `get_export_location()`: CephFS export path 조회
  - `get_cephx_credentials()`: access rule에서 CephX key 추출
- `GET /api/shares`: 사전 빌드된 라이브러리 share 목록
- `GET /api/libraries`: 사용 가능한 라이브러리 설정 (의존성 그래프 포함)

### 5단계: Backend — cloud-init 엔진 + OverlayFS 템플릿

- `services/cloudinit.py`: Jinja2 기반 cloud-init userdata 생성기
  - 라이브러리 의존성 토폴로지 정렬 → lowerdir 순서 결정
  - CephX 크리덴셜 base64 인코딩 → write_files 삽입
  - Strategy A/B 분기 처리
- `templates/overlay_setup.sh.j2`:
  - CephFS 마운트 (커널 드라이버 우선, ceph-fuse 폴백)
  - OverlayFS 구성 (lowerdir 체인, upperdir, workdir)
  - `/usr/local`과 `/opt`에 마운트
- `templates/cloudinit_base.yaml.j2`:
  - write_files: ceph keyring, overlay 스크립트, systemd unit
  - runcmd: systemctl enable/start
- `templates/strategy_dynamic.sh.j2`:
  - pip install 명령 생성 (라이브러리별 버전 포함)
  - 설치 완료 후 OverlayFS 재구성

### 6단계: Backend — 인스턴스 오케스트레이션 (핵심)

- `POST /api/instances`: VM 생성 전체 흐름 구현
  1. Manila: access rule 생성(A) 또는 신규 share 생성(B)
  2. Cinder: 부트 볼륨 생성 (선택된 OS 이미지 기반)
  3. Cinder: upperdir용 볼륨 생성
  4. cloud-init userdata 생성 (CephX 크리덴셜 주입)
  5. Nova: 서버 생성 (block_device_mapping_v2)
- 실패 시 역순 rollback 로직 (이전 단계 리소스 정리)
- `DELETE /api/instances/{id}`: VM 삭제 + Manila share/access rule 정리 + Cinder 볼륨 삭제
- `GET /api/instances`: VM 목록 (Manila 메타데이터 포함)
- `GET /api/instances/{id}`: VM 상세 정보
- JSON 파일 또는 SQLite로 VM-리소스 매핑 관리 (어떤 VM이 어떤 share/volume을 사용하는지)

### 7단계: Frontend — SvelteKit 기본 구조 + 인증

- 레이아웃: `+layout.svelte` (네비게이션 바, 인증 상태)
- `stores/auth.ts`: Svelte writable store (토큰, 사용자 정보)
- `lib/api/client.ts`: Backend API 클라이언트 (fetch wrapper, 토큰 자동 첨부)
- `routes/+page.svelte`: 로그인 페이지 (Keystone 인증 폼)
- 인증 guard: 로그인 안 된 경우 리다이렉트

### 8단계: Frontend — 대시보드 + VM 관리

- `routes/dashboard/+page.svelte`: VM 목록 테이블
  - 상태(ACTIVE/BUILD/SHUTOFF), 이미지, 플레이버, 라이브러리 표시
  - 10초 간격 자동 새로고침
  - 액션 버튼: 시작/정지/삭제/콘솔
- VM 상세 모달/페이지: Manila share 정보, OverlayFS 상태
- 삭제 확인 다이얼로그

### 9단계: Frontend — VM 생성 Wizard (5단계)

- `stores/wizard.ts`: wizard 상태 관리 (선택된 이미지/플레이버/라이브러리/전략)
- `components/wizard/SelectImage.svelte`: OS 이미지 카드 선택
- `components/wizard/SelectFlavor.svelte`: 플레이버 선택 (CPU/RAM/GPU 표시)
- `components/wizard/SelectLibraries.svelte`: 라이브러리 체크박스 (의존성 자동 체크, GPU 경고)
- `components/wizard/SelectStrategy.svelte`: 전략 A/B 선택 (장단점 비교 UI)
- `components/wizard/ReviewDeploy.svelte`: 최종 요약 + 배포 버튼
- `routes/create/+page.svelte`: wizard 컨테이너 (단계 네비게이션)

### 10단계: Admin 기능 + 사전 빌드 share 관리

- `scripts/build_library_shares.py`: CLI 도구
  - Manila share 생성 → 임시 VM 부팅 → pip install → share에 기록 → VM 삭제
  - 라이브러리별 버전 설정 파일 (`libraries.yaml`)
- `POST /api/admin/shares/build`: 웹에서 사전 빌드 트리거
- `routes/admin/+page.svelte`: Admin 페이지
  - 사전 빌드 share 목록, 상태, 마지막 빌드 시간
  - 빌드/업데이트 버튼
  - 라이브러리 설정 편집

### 11단계: Docker 통합 + 최종 검증

- `docker-compose.yml`: frontend(node) + backend(uvicorn) 컨테이너
- Backend `Dockerfile`: Python + requirements 설치
- Frontend: SvelteKit build → node adapter
- Nginx 설정 (프록시): `/` → frontend, `/api` → backend
- `.env.example` 최종 정리

---

## 검증 체크리스트

- [ ] Keystone 로그인 → 이미지/플레이버 목록 조회
- [ ] VM 생성 (Strategy A) → ssh 접속 → `mount | grep overlay` 확인
- [ ] VM 생성 (Strategy B) → ssh 접속 → `mount | grep overlay` 확인
- [ ] `python3 --version`, `import torch`, `jupyter` 실행 확인
- [ ] VM 삭제 → Manila share/Cinder volume 정리 확인
- [ ] cloud-init userdata 유효성: `cloud-init devel schema --config-file`
- [ ] 재부팅 후 OverlayFS 자동 재마운트 확인 (systemd)

---

## 1. Manila NFS Share 지원 추가

> **목표**: 기존 CephFS 전용 Manila 연결을 NFS 프로토콜로 확장하여, VM에서 NFS 마운트로 파일 스토리지 접근 가능하게 구현

- [x] 1.1 Manila NFS share 생성 기능 구현
  - [x] `share_proto="NFS"` 옵션으로 Manila share 생성 API 연동
  - [x] NFS 전용 share type 지원 (`nfstype` 등 환경별 설정)
  - [x] `backend/app/services/manila.py` — NFS share 생성/삭제/조회 함수 추가
  - [x] `backend/app/models/storage.py` — NFS 관련 필드 추가 (`share_proto`, `nfs_export_location`)
  - [x] `config.toml.example` — NFS용 설정 항목 추가 (`os_manila_nfs_share_type`)

- [x] 1.2 NFS access rule 관리
  - [x] NFS access rule 생성: `access_type="ip"`, `access_to="<VM_IP_OR_CIDR>"`
  - [x] VM Floating IP / Tenant 네트워크 CIDR 기반 자동 access rule 등록
  - [x] VM 생성 시 인스턴스 IP 확보 후 NFS share access rule 자동 추가
  - [ ] VM 삭제 시 관련 NFS access rule 자동 정리 (기존 access rule 정리 로직에 NFS 케이스 추가 필요)

- [x] 1.3 NFS 마운트 안정성 확보
  - [x] NFS 마운트 옵션 튜닝: `hard,intr,noatime,_netdev` 기본값
  - [x] 재연결 정책: `timeo=10,retrans=3` 으로 일시적 네트워크 장애 대응
  - [x] systemd 마운트 유닛(`union-overlay.service`) — `After=network-online.target remote-fs.target`
  - [ ] NFS 마운트 상태 헬스체크 스크립트 추가 (5.1로 이동)

- [ ] 1.4 Frontend — NFS 옵션 UI
  - [ ] 파일 스토리지 생성 시 프로토콜 선택 (CEPHFS / NFS) 드롭다운 추가
  - [ ] NFS share 목록 및 access rule 관리 UI
  - [ ] VM 생성 마법사에서 마운트 프로토콜 선택 옵션

---

## 2. Union Mount (OverlayFS) 재설계 및 구현

> **목표**: Manila share(NFS) 레이어를 `/opt/layers/lower/`에 순차 마운트하고, `/opt/layers/upper/`와 함께 `/opt/layers/merged/`에 OverlayFS로 통합 마운트

### 2.1 Lower Layer — NFS 마운트

- [x] 2.1.1 디렉토리 구조 표준화
  ```
  /opt/layers/
  ├── lower/                    # 읽기 전용 레이어 (NFS 마운트 포인트)
  │   ├── python311/            # Python 3.11 레이어
  │   ├── torch/                # PyTorch 레이어
  │   ├── vllm/                 # vLLM 레이어
  │   └── jupyter/              # Jupyter 레이어
  ├── upper/                    # 쓰기 가능 레이어 (Cinder 볼륨)
  ├── work/                     # OverlayFS workdir
  └── merged/                   # OverlayFS 병합 마운트 포인트
  ```

- [x] 2.1.2 cloud-init 템플릿 재작성 (`overlay_setup.sh.j2`)
  - [x] CephFS 마운트 → NFS 마운트 전환 (프로토콜 자동 감지)
  - [x] `/opt/layers/lower_<lib_name>` 에 순차적 NFS 마운트
  - [x] 각 레이어 마운트 순서: 의존성 토폴로지 정렬 (기존 `libraries.py` 로직 활용)
  - [x] 마운트 실패 시 재시도 로직 (최대 30회, 5초 간격)
  - [x] NFS 마운트 vs CephFS 마운트 분기 처리

- [x] 2.1.3 프로토콜 자동 감지 로직
  - [x] Manila share `share_proto` 필드 기반 분기
  - [x] NFS: `mount -t nfs <export_location> /opt/layers/lower_<name>`
  - [x] CephFS: 기존 `mount -t ceph` 또는 `ceph-fuse` 로 폴백
  - [x] `cloudinit.py` — `generate_userdata()` 에 프로토콜 정보 전달

### 2.2 OverlayFS 마운트 — `/opt/layers/merged/`

- [x] 2.2.1 단일 OverlayFS 마운트 구현
  ```bash
  mount -t overlay overlay \
    -o "lowerdir=/opt/layers/lower/vllm:/opt/layers/lower/torch:/opt/layers/lower/python311,upperdir=/opt/layers/upper,workdir=/opt/layers/work" \
    /opt/layers/merged
  ```
  - [x] lowerdir 순서: 의존성이 높은 레이어가 우선 (왼쪽)
  - [x] 기존 `/usr/local` 및 `/opt` 개별 overlay → 단일 `/opt/layers/merged` 로 통합
  - [ ] 기본 OS lowerdir 포함 여부 결정 (필요시 `/usr/local` 원본을 마지막 lowerdir로)

- [x] 2.2.2 OverlayFS systemd 유닛 재설계
  - [x] `union-overlay.service`: 네트워크/원격 파일시스템 의존성 추가
    ```ini
    [Unit]
    After=network-online.target remote-fs.target
    Requires=network-online.target
    ```
  - [x] `After=remote-fs.target` — NFS 마운트 완료 후 OverlayFS 시작 보장
  - [x] 마운트 실패 시 자동 복구 로직 (`OnFailure=emergency.target`)

- [x] 2.2.3 Cinder 볼륨 upperdir 구성
  - [x] `/dev/vdb` (또는 설정 가능) 블록 장치 → `/opt/layers/upper` 마운트
  - [x] 최초 마운트 시 ext4 포맷 (`mkfs.ext4 -F`)
  - [x] `/opt/layers/upper` 및 `/opt/layers/work` 하위 디렉토리 자동 생성

### 2.3 마운트된 디렉토리 환경변수 등록

> **조사 결론**: `/usr/local` 심볼릭 링크 방식은 기존 시스템 바이너리와 충돌 위험이 있어 **하이브리드 방식**을 추천

- [x] 2.3.1 `/etc/profile.d/union-env.sh` — PATH 및 환경변수 설정
  ```bash
  export PATH="/opt/layers/merged/usr/local/bin:/opt/layers/merged/bin:$PATH"
  export LD_LIBRARY_PATH="/opt/layers/merged/usr/local/lib:/opt/layers/merged/usr/local/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export PYTHONPATH="/opt/layers/merged/usr/local/lib/python3.11/site-packages${PYTHONPATH:+:$PYTHONPATH}"
  export PKG_CONFIG_PATH="/opt/layers/merged/usr/local/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  ```
  - [x] 로그인 셸 + 대화형 셸에 적용
  - [x] 라이브러리별 Python 버전에 따라 PYTHONPATH 동적 생성

- [x] 2.3.2 `/etc/environment` 업데이트 — 시스템 서비스에도 적용
  - [x] systemd 서비스(SSHD 등)가 overlay 경로의 바이너리를 찾을 수 있도록 `/etc/environment` 갱신

- [ ] 2.3.3 선택적 심볼릭 링크 생성 (보조)
  - [ ] `/opt/layers/merged/bin/python3` → `/usr/local/bin/python3` 심볼릭 링크
  - [ ] 기존 `/usr/local` 백업 후 심볼릭 링크 교체는 고위험 → profile.d 방식 우선
  - [ ] 관리자 옵션으로 `--symlink-mode` 제공 (호환성 필요 시)

- [x] 2.3.4 환경변수 템플릿 (`cloudinit_base.yaml.j2` 수정)
  - [x] `write_files` 에 `union-env.sh` 추가
  - [x] 라이브러리 의존성에 따른 PYTHONPATH 동적 구성
  - [x] GPU 관련 환경변수 (`CUDA_HOME`, `LD_LIBRARY_PATH` 등) 조건부 추가

---

## 3. 사전 패키지(Pre-built Library) 관리 시스템

> **목표**: Admin 프로젝트에서 사전 빌드된 라이브러리 패키지(NFS share)를 생성하고, 다른 프로젝트에서도 read-only로 사용 가능하게 구현

- [ ] 3.1 Admin 프로젝트 — 패키지 생성 API
  - [ ] `POST /api/admin/libraries/build` — 라이브러리 패키지 빌드 트리거
  - [ ] 기존 `POST /api/admin/file-storage/build` 확장:
    - [x] `share_proto` 파라미터 추가 (CEPHFS / NFS 선택)
    - [x] 의존성 메타데이터 `union_depends_on` 필드 추가
    - [ ] 빌드 상태 관리: `building` → `ready` / `failed` 상태 전이
  - [ ] `GET /api/admin/libraries` — 전체 프로젝트 가용 라이브러리 목록 (의존성 포함)
  - [ ] `GET /api/admin/libraries/{id}` — 라이브러리 상세 (의존성 트리 포함)

- [x] 3.2 Manila 메타데이터 기반 의존성 추적
  - [x] Manila share metadata 활용:
    ```json
    {
      "union_type": "prebuilt",
      "union_library": "vllm",
      "union_version": "0.6.0",
      "union_depends_on": "python311,torch",
      "union_python_version": "3.11",
      "union_ubuntu_versions": "22.04,24.04",
      "union_share_proto": "NFS",
      "union_status": "ready"
    }
    ```
  - [x] `LibraryConfig` 모델 확장: `share_proto`, `ubuntu_versions` 필드 추가
  - [ ] 의존성 검증 로직: 선택된 라이브러리 조합이 호환 가능한지 확인

- [x] 3.3 크로스 프로젝트 접근 관리
  - [x] Admin 프로젝트에서 NFS share 생성 시 다른 프로젝트 접근 허용:
    - [x] Manila share를 `public` 으로 설정 (`is_public=True`) — `set_share_public()` API 구현
    - [ ] 특정 프로젝트에 대해 개별적으로 NFS access rule 부여 (VM IP/CIDR 자동 계산 미구현)
    - [ ] VM 생성 시 해당 프로젝트의 네트워크 CIDR로 NFS access rule 자동 생성
  - [x] CephFS의 경우: 기존 CephX access rule 방식 유지
  - [ ] `backend/app/services/libraries.py` — 크로스 프로젝트 라이브러리 조회 함수 추가

- [x] 3.4 패키지 빌드 파이프라인 개선
  - [x] `scripts/build_library_shares.py` 확장:
    - [x] NFS share 빌드 지원 (`--proto NFS` 옵션)
    - [x] 의존성 메타데이터 자동 기록
    - [ ] 빌드 완료 후 자동 검증 (마운트 테스트)
  - [ ] 백그라운드 빌드 워커 (선택): Celery/async 작업으로 비동기 빌드

- [ ] 3.5 Frontend — Admin 패키지 관리 UI
  - [ ] `routes/admin/libraries/+page.svelte` — 라이브러리 카탈로그 관리 페이지
  - [ ] 패키지 빌드 상태 표시 (building / ready / failed)
  - [ ] 의존성 그래프 시각화
  - [ ] 패키지 공개/비공개 설정 (다른 프로젝트 접근 권한)
  - [ ] 기존 `routes/admin/file-storage/+page.svelte`에 프로토콜 컬럼 추가

- [ ] 3.6 VM 생성 마법사 — 라이브러리 선택 개선
  - [ ] 의존성 자동 해석: vllm 선택 시 torch, python311 자동 체크
  - [ ] 호환성 검증: Ubuntu 버전 / Python 버전 충돌 시 경고
  - [ ] 마운트 프로토콜 표시 (NFS / CephFS)

---

## 4. Cinder 볼륨 마이그레이션 (프로젝트 간)

> **목표**: 프로젝트 간 볼륨 이전 기능 ( Cinder volume transfer )

- [x] 4.1 Cinder 볼륨 Transfer API 연동
  - [x] `backend/app/services/cinder.py` — Transfer 관련 함수 추가:
    - [x] `create_volume_transfer()` — 볼륨 이전 생성 (auth token 포함)
    - [x] `accept_volume_transfer()` — 볼륨 이전 수락
    - [x] `list_volume_transfers()` — 이전 목록 조회
    - [x] `delete_volume_transfer()` — 이전 취소
  - [ ] VM에 연결된 볼륨은 마이그레이션 전 detach 필요

- [x] 4.2 API 엔드포인트
  - [x] `POST /api/volumes/{id}/transfer` — 이전 생성
  - [x] `POST /api/volumes/transfer/{transfer_id}/accept` — 이전 수락
  - [x] `GET /api/volumes/transfers` — 이전 목록
  - [x] `DELETE /api/volumes/transfer/{transfer_id}` — 이전 취소

- [ ] 4.3 Frontend — 볼륨 마이그레이션 UI
  - [ ] 볼륨 상세 페이지에 "이전" 버튼 추가
  - [ ] 대상 프로젝트 선택 및 auth key 입력 폼
  - [ ] 이전 진행 상태 표시

---

## 5. 클라우드 운영 추가 기능

> **목표**: 프로덕션 환경 운영에 필요한 기능 추가

- [ ] 5.1 OverlayFS 상태 모니터링 에이전트
  - [ ] VM 내부 헬스체크 스크립트 (`/opt/union/scripts/health-check.sh`)
  - [ ] 마운트 상태: `mountpoint -q /opt/layers/merged` 확인
  - [ ] NFS 연결 상태: `rpcinfo -p <nfs_server>` 또는 `nfsstat` 확인
  - [ ] 디스크 사용량: upper 볼륨 사용률 경고 (임계치 설정 가능)
  - [ ] 결과를 Nova metadata 또는 별도 API로 리포트

- [ ] 5.2 Manila Share Snapshot 관리
  - [ ] 사전 빌드 라이브러리의 스냅샷 생성/복원 기능
  - [ ] 버전 업데이트 시 스냅샷으로 롤백 가능
  - [ ] `backend/app/services/manila.py` — 스냅샷 API 연동

- [ ] 5.3 볼륨 백업 및 복구
  - [ ] Cinder upper 볼륨의 정기 백업 스케줄링
  - [ ] 백업에서 복구 시 OverlayFS 재구성 자동화

- [ ] 5.4 VM 스케일링 지원
  - [ ] 인스턴스 resize (플레이버 변경) 시 OverlayFS 마운트 유지
  - [ ] 다중 VM 동시 부팅 시 NFS share 동시 접근 안정성 검증
  - [ ] 라이선스/동시 접속 제한 검토 (상용 소프트웨어)

- [ ] 5.5 보안 강화
  - [ ] NFS export 옵션 보안: `root_squash`, `sec=sys` vs `sec=krb5`
  - [ ] CephX 키 로테이션 지원
  - [ ] VM 간 데이터 격리 검증 (다른 프로젝트의 share 접근 차단)
  - [ ] NFS 방화벽 규칙 자동 관리 (Security Group)

- [ ] 5.6 로깅 및 감사
  - [ ] 마운트/언마운트 이벤트 로깅
  - [ ] 라이브러리 사용 통계 (어떤 라이브러리가 어떤 VM에 마운트되었는지)
  - [ ] 관리자 대시보드에 라이브러리 사용량 차트 추가

---

## 구현 우선순위

| 순서 | 항목 | 예상 소요 | 비고 |
|------|------|-----------|------|
| 1 | 1.1~1.3 — NFS share 생성 및 마운트 | 3일 | Manila API 확장 + cloud-init |
| 2 | 2.1~2.2 — OverlayFS 단일 마운트 구조 | 2일 | 템플릿 재작성 |
| 3 | 2.3 — 환경변수 등록 | 1일 | profile.d + 환경변수 |
| 4 | 3.1~3.3 — 크로스 프로젝트 패키지 관리 | 3일 | 메타데이터 + access rule |
| 5 | 1.4 + 3.5 — Frontend UI | 3일 | NFS 옵션 + 라이브러리 관리 |
| 6 | 4.1~4.3 — 볼륨 마이그레이션 | 2일 | Cinder Transfer API |
| 7 | 5.1~5.6 — 운영 기능 | 5일 | 모니터링 + 보안 + 로깅 |

**총 예상 소요: 약 19일**

---

## 개발 규칙 및 작업 지시사항

### 2026-04-16 — pieroot 관리자 접근 불가 버그 수정

**문제**: `pieroot` 계정이 admin 프로젝트에서 admin role 을 보유하고 있음에도 관리자 페이지 접근 불가. `admin` 계정은 정상 동작.

**원인**: 기존 코드가 scoped token 의 role_names(현재 프로젝트 기준)로 관리자 판별. pieroot 의 default project 가 admin 이 아니어서 scoped token 에 "admin" role 이 없었음.

**수정 내용**:
- [x] `backend/app/services/keystone.py` — `_is_system_admin(user_id)` 신설. 서비스 admin 크리덴셜로 `role_assignments.list` 조회 → scoped project 무관하게 admin 프로젝트의 admin role 보유 여부 판정.
- [x] `backend/app/api/deps.py::require_admin` — scoped role 체크 제거, `is_system_admin` 사용.
- [x] `backend/app/api/identity/auth.py::login, gitlab_callback` — `is_system_admin` 필드 포함 응답.
- [x] `backend/app/models/auth.py` — `TokenResponse`, `UserInfo` 에 `is_system_admin: bool = False` 추가.
- [x] `backend/app/api/identity/auth.py::me` — `UserInfo` 에 `is_system_admin` 포함 반환 (페이지 새로고침 후 localStorage 동기화).
- [x] `frontend/src/lib/stores/auth.ts` — `isSystemAdmin: boolean` 상태 + `isAdmin = isSystemAdmin === true`.
- [x] `frontend/src/routes/+layout.svelte` — onMount 에서 `/api/auth/me` 응답으로 `isSystemAdmin` 재동기화 (구버전 localStorage 대응).
- [x] `frontend/src/routes/+page.svelte`, `auth/gitlab/callback/+page.svelte` — 로그인 응답에서 `isSystemAdmin` 설정.
- [x] `backend/tests/integration/credentials.py` — `admin_user_credentials()` 로더 추가 (`[admin_user]` 섹션).
- [x] `backend/tests/integration/conftest.py` — `admin_user_credentials_fx`, `admin_user_auth_data`, `admin_user_client` 픽스처 추가.
- [x] `backend/tests/integration/test_auth.py` — `test_admin_user_login_is_system_admin`, `test_admin_user_me_returns_is_system_admin` 테스트 추가.
- [x] `backend/tests/integration/test_admin.py` — `test_admin_user_can_access_admin_*` 3개 회귀 테스트 추가.

### 2026-04-16 — 개발 규칙 추가 (CLAUDE.md 갱신)

- [x] 백엔드 엔드포인트 구현 시 테스트 코드 작성 의무화
  - Mock으로만 때우는 테스트 금지 — 실제 로직을 검증하는 테스트 필수
  - `tests/test_*.py` (단위) 또는 `tests/integration/test_*.py` (통합) 중 하나 이상 필수
  - 에러 케이스, 권한 없음, 존재하지 않는 리소스 등 엣지 케이스 커버 필수
  - 테스트 없이 완료 처리 불가
- [x] 모든 작업 내용 milestone.md 기재 의무화
  - 완료 항목 즉시 `[x]` 체크
  - 중간 지시 작업도 milestone.md에 섹션 추가하여 기록

---

## 2026-04-16 — 인프라 정비 (GitHub Actions self-hosted, Manila quota 수정, Ruff, 통합 테스트 러너)

### Manila 쿼타 404 버그 수정

**근본 원인**: `app/services/manila.py::_get_manila_endpoint()` 의 service_type 검색 순서가 `("share", "sharev2", ...)` 로 v1 endpoint 먼저 반환. Manila v1에서는 quota-sets path 가 `os-quota-sets` 였으므로 v2 microversion 헤더를 보내도 URL 자체가 404.

- [x] `backend/app/services/manila.py` — `_normalize_manila_url()` 추가 (v1 → v2 path 정규화), `_get_manila_endpoint()` 검색 순서 변경 (`sharev2` 우선)
- [x] `backend/tests/test_file_storage.py` — URL 정규화/우선순위 단위 테스트 3개 추가
- [x] `backend/tests/integration/test_file_storage.py` — quota 응답 구조 검증 강화

### GitHub Actions self-hosted matrix + 멀티플랫폼 manifest

- [x] `.github/workflows/test.yml` — **신규**: GitHub Actions 단위 테스트 워크플로우 (backend + frontend, ubuntu-latest)
- [x] `.github/workflows/docker-build.yml` — self-hosted matrix (linux/amd64, macos/arm64) + per-arch build + manifest 통합 job으로 재구성. Apple Silicon native pull 지원.

### CI 테스트 분리

- [x] `.github/workflows/test.yml` — 통합 테스트(`tests/integration`) 제외하고 단위 테스트만 CI 실행 (GitLab CI는 이미 `--ignore=tests/integration` 으로 분리되어 있음)
- [x] `.gitlab-ci.yml::test-backend` — ruff check + format check 단계 추가

### Ruff 자동화 (백엔드)

- [x] `backend/pyproject.toml` — `ruff>=0.7.0` dev 의존성 추가, `[tool.ruff]` / `[tool.ruff.lint]` / `[tool.ruff.format]` 설정 추가
- [x] `.pre-commit-config.yaml` — **신규**: ruff hook (백엔드 한정)
- [x] 초기 포맷 자동 적용: `ruff check --fix` + `ruff format` 실행 (476개 자동 수정)

### 통합 테스트 러너 (루트 package.json)

- [x] `package.json` — **신규**: 루트 monorepo 테스트 러너 (`npm test`, `npm run test:backend`, `npm run test:frontend`, `npm run test:all`, `npm run test:parallel`, `npm run lint:backend`)
- [x] `.gitignore` — `/node_modules/` 추가

## 7. 버전 관리 통합 + GitHub Actions 수정

> **목표**: 루트 `package.json` 을 단일 버전 진실 소스로 만들고, CI 에서 불일치 시 빌드 차단, PR 은 이미지 미푸시

- [x] 7.1 버전 초기 동기화 (1.13.0 → 1.13.2)
  - [x] `backend/pyproject.toml` — `1.13.0` → `1.13.2`
  - [x] `frontend/package.json` — `1.13.0` → `1.13.2`
  - [x] `backend/uv.lock` — `uv lock` 재생성으로 1.13.2 반영

- [x] 7.2 Node 기반 버전 동기화 스크립트
  - [x] `scripts/sync-version.js` — 루트 package.json → frontend/backend/uv.lock 전파
  - [x] `scripts/check-version-sync.js` — CI 용 일치 검증 (tag push 시 git ref 비교)
  - [x] `package.json` — `version`, `version:sync`, `version:check`, `version:bump:patch/minor/major` 스크립트 추가
  - [x] npm `version` 훅으로 `npm version patch/minor/major` 한 번에 모든 파일 동기화

- [x] 7.3 백엔드 `_read_app_version` 중복 제거
  - [x] `backend/app/utils/version.py` — `read_app_version()` 공용 유틸 신규 생성
  - [x] `backend/app/main.py` — 로컬 `_read_app_version()` 제거, util import 로 치환
  - [x] `backend/app/api/identity/admin.py` — 로컬 `_read_backend_version()` 제거, util import 로 치환

- [x] 7.4 GitHub Actions 문제 수정
  - [x] `docker-build.yml` — PR 에서 `push: false`, `cache-to` 도 PR skip
  - [x] `docker-build.yml` — manifest job 에 `if: github.event_name != 'pull_request'` 가드 추가
  - [x] `docker-build.yml` — checkout 직후 `check-version-sync.js` 검증 스텝 삽입 (tag push 시 git tag ↔ package.json 일치 확인)
  - [x] `test.yml` — 트리거에 `dev` 브랜치 및 `v*` 태그 추가
  - [x] `test.yml` — `version-check` job 신설, `test-backend`/`test-frontend` 가 `needs: version-check` 로 직렬화

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
