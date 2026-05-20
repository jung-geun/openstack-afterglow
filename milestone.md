# Afterglow 프로젝트 마일스톤

---

## 0. 프로젝트 개요 (구 PLAN.md) ⚠️ 구 설계, union.md로 대체됨

> **[DEPRECATED]** 이 섹션은 초기 설계 문서(PLAN.md)를 이전한 내용으로, OverlayFS 레이어 시스템의 구 설계를 담고 있습니다.
> 현재 설계는 **`union.md`** (Content-addressable 불변 레이어, single-parent 상속, Manila 3개 share)를 참조하세요.
> 아래 내용은 역사적 참조용으로만 보존합니다.

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
| POST | `/api/images` | 이미지 파일 업로드 (multipart, raw/qcow2/vmdk 등) |
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
  - [x] VM 삭제 시 관련 NFS access rule 자동 정리 — `delete_instance()`에서 VM IP 매칭 후 revoke (best-effort)

- [x] 1.3 NFS 마운트 안정성 확보
  - [x] NFS 마운트 옵션 튜닝: `hard,intr,noatime,_netdev` 기본값
  - [x] 재연결 정책: `timeo=10,retrans=3` 으로 일시적 네트워크 장애 대응
  - [x] systemd 마운트 유닛(`union-overlay.service`) — `After=network-online.target remote-fs.target`
  - [ ] NFS 마운트 상태 헬스체크 스크립트 추가 (5.1로 이동)

- [x] 1.4 Frontend — NFS 옵션 UI
  - [x] 파일 스토리지 생성 시 프로토콜 선택 (CEPHFS / NFS) 드롭다운 추가
  - [x] NFS share 목록 및 access rule 관리 UI
  - [x] VM 생성 마법사에서 마운트 프로토콜 선택 옵션 — `SelectStrategy.svelte` Strategy B에 NFS/CephFS 토글, `wizard.ts` mountProtocol 상태 추가, 라이브러리별 프로토콜 배지

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

- [x] 3.1 Admin 프로젝트 — 패키지 생성 API
  - [x] `POST /api/admin/libraries/build` — 라이브러리 패키지 빌드 트리거 (`auto_install` 옵션)
  - [x] 기존 `POST /api/admin/file-storage/build` 확장:
    - [x] `share_proto` 파라미터 추가 (CEPHFS / NFS 선택)
    - [x] 의존성 메타데이터 `union_depends_on` 필드 추가
    - [x] 빌드 상태 관리: `building` → `ready` / `failed` / `cancelled` 상태 전이, `cancel_build()` 구현
  - [x] `GET /api/admin/libraries` — 전체 프로젝트 가용 라이브러리 목록 (의존성 포함)
  - [x] `GET /api/admin/libraries/{id}` — 라이브러리 상세 (의존성 트리 포함)
  - [x] `GET /api/admin/libraries/builds` — 빌드 이력 목록 (DB + 인메모리 fallback)
  - [x] `POST /api/admin/libraries/builds/{id}/cancel` — 빌드 취소 (VM 정리 포함)
  - [x] `backend/app/api/identity/admin_libraries.py` — 전용 라우터 신규 구현 (관리자 인증 필수)

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
  - [x] 의존성 검증 로직: `validate_compatibility()`, `check_python_version_conflict()` — Ubuntu 버전 / Python 버전 충돌 감지. `POST /api/libraries/validate` 엔드포인트 추가

- [x] 3.3 크로스 프로젝트 접근 관리
  - [x] Admin 프로젝트에서 NFS share 생성 시 다른 프로젝트 접근 허용:
    - [x] Manila share를 `public` 으로 설정 (`is_public=True`) — `set_share_public()` API 구현
    - [x] VM 생성 시 해당 프로젝트의 네트워크 CIDR로 NFS access rule 자동 생성 — `_prepare_prebuilt_file_storages`에 NFS 분기 추가, service project conn으로 `ensure_nfs_access_rule` 호출
    - [x] `POST /api/admin/libraries/{id}/project-access` — 관리자 수동 CIDR grant (idempotent)
    - [x] `DELETE /api/admin/libraries/{id}/project-access/{project_id}` — 관리자 수동 revoke (`union_grant_project` metadata로 식별)
    - [x] `GET /api/admin/libraries/{id}/project-access` — 프로젝트별 grant 목록 조회
  - [x] CephFS의 경우: 기존 CephX access rule 방식 유지
  - [x] VM 삭제 cleanup: prebuilt cephx rule은 service conn으로 revoke, NFS CIDR rule은 lifecycle A(관리자 수동 revoke)
  - [x] `backend/app/services/libraries.py` — `get_dependency_tree()` 크로스 프로젝트 라이브러리 의존성 트리 조회 함수 추가

- [x] 3.4 패키지 빌드 파이프라인 개선
  - [x] `scripts/build_library_shares.py` 확장:
    - [x] NFS share 빌드 지원 (`--proto NFS` 옵션)
    - [x] 의존성 메타데이터 자동 기록
    - [x] 빌드 완료 후 자동 검증 (마운트 테스트) — probe VM (`_verify_layer_accessible`) VERIFY_OK/FAIL 판별 후 status=error 전환
  - [x] 백그라운드 빌드 워커: asyncio.Queue 기반 큐(`queue_build`/`_build_worker`/`get_build_queue_status`) + main.py 시작 시 워커 자동 실행

- [x] 3.5 Frontend — Admin 패키지 관리 UI
  - [x] `routes/admin/libraries/+page.svelte` — 라이브러리 카탈로그 관리 페이지 (카드 그리드)
  - [x] 패키지 빌드 상태 표시 (building / ready / failed / none)
  - [x] 빌드 트리거 버튼 + AutoRefresh (10초)
  - [x] 의존성 배지 표시
  - [x] 의존성 그래프 시각화 (SVG 연결선) — 레벨 기반 DAG, 빌드 상태 색상, 노드 클릭 스크롤
  - [x] 패키지 공개/비공개 설정 — `visibility` 필드 추가, non-admin은 public만 반환

- [x] 3.6 VM 생성 마법사 — 라이브러리 선택 개선
  - [x] 의존성 자동 해석: vllm 선택 시 torch, python311 자동 체크 (전이적 DFS 해결)
  - [x] 호환성 검증: Ubuntu 버전 / Python 버전 충돌 시 경고 (`POST /api/libraries/validate` 연동, debounce 300ms)
  - [x] 마운트 프로토콜 표시 (NFS / CephFS) — SelectLibraries.svelte에 이미 구현됨

---

## 4. Cinder 볼륨 마이그레이션 (프로젝트 간)

> **목표**: 프로젝트 간 볼륨 이전 기능 ( Cinder volume transfer )

- [x] 4.1 Cinder 볼륨 Transfer API 연동
  - [x] `backend/app/services/cinder.py` — Transfer 관련 함수 추가:
    - [x] `create_volume_transfer()` — 볼륨 이전 생성 (auth token 포함)
    - [x] `accept_volume_transfer()` — 볼륨 이전 수락
    - [x] `list_volume_transfers()` — 이전 목록 조회
    - [x] `delete_volume_transfer()` — 이전 취소
  - [x] VM에 연결된 볼륨은 마이그레이션 전 detach 필요 — `POST /api/volumes/{id}/transfer` 자동 detach + `cinder.wait_volume_available` 대기 + transfer 실패 시 rollback attach 구현. 단위테스트 9건(`test_volume_transfer.py`)

- [x] 4.2 API 엔드포인트
  - [x] `POST /api/volumes/{id}/transfer` — 이전 생성
  - [x] `POST /api/volumes/transfer/{transfer_id}/accept` — 이전 수락
  - [x] `GET /api/volumes/transfers` — 이전 목록
  - [x] `DELETE /api/volumes/transfer/{transfer_id}` — 이전 취소

- [x] 4.3 Frontend — 볼륨 마이그레이션 UI
  - [x] 볼륨 목록 `available` 상태 행에 "이전" 버튼 추가
  - [x] `VolumeTransferModal.svelte` — 이전 생성(auth_key 복사)/수락(transfer_id+auth_key)/목록+취소
  - [x] `cinder.py` Transfer 서비스 함수 4개 구현 (이전에 누락되어 런타임 500 발생하던 버그 수정)

---

## 5. 클라우드 운영 추가 기능

> **목표**: 프로덕션 환경 운영에 필요한 기능 추가

- [x] 5.1 OverlayFS 상태 모니터링 에이전트
  - [x] VM 내부 헬스체크 스크립트 (`/opt/union/scripts/health-check.sh`)
  - [x] 마운트 상태: `mountpoint -q /opt/layers/merged` 확인
  - [x] NFS/CephFS 연결 상태: `timeout 5 stat` (hard mount hang 방지)
  - [x] 디스크 사용량: upper 볼륨 사용률 경고 (90%/95% 임계)
  - [x] 결과를 backend API (`POST /api/instances/{id}/health/report`)로 리포트 (Bearer 토큰 인증, 30분 TTL Redis 캐시)

- [x] 5.2 Manila Share Snapshot 관리
  - [x] 사전 빌드 라이브러리의 스냅샷 생성/복원 기능 (`POST /api/share-snapshots`, `POST /api/share-snapshots/{id}/revert`)
  - [x] 버전 업데이트 시 스냅샷으로 롤백 가능 (`revert_to_snapshot` — Manila action API)
  - [x] `backend/app/services/manila.py` — 스냅샷 API 연동 (create/list/get/delete/revert 5개 함수)

- [x] 5.3 볼륨 백업 및 복구
  - [x] Cinder upper 볼륨의 정기 백업 스케줄링 — `auto_backup.py` + `_auto_backup_loop`
  - [x] 백업에서 복구 시 OverlayFS 재구성 자동화 — `existing_upper_volume_id` + workdir 정리
  - [x] 볼륨 목록 ActionMenu 수동 백업 생성 — `VolumeBackupModal.svelte` + `POST /api/volumes/backups` (기존 endpoint 재사용)
  - [x] 볼륨 목록 ActionMenu 스냅샷 생성 — `VolumeSnapshotModal.svelte` + `POST /api/volume-snapshots` (기존 endpoint 재사용)
  - [x] 사용자용 볼륨 용량 확장 — `POST /api/volumes/{id}/extend` + `cinder.extend_volume` + `VolumeExtendModal.svelte` (available + in-use 모두 허용, 단위 테스트 7건)

- [x] 5.4 VM 스케일링 지원
  - [x] 인스턴스 resize (플레이버 변경) — `POST /api/admin/instances/{id}/resize`, `/revert-resize` 엔드포인트 + `nova.resize_server`/`revert_resize_server` 서비스 함수 추가. `InstanceDetailPanel`에 resize 모달(flavor 선택) + VERIFY_RESIZE 상태에서 '되돌리기' 버튼 추가. 단위 테스트 4건 (`test_admin_resize.py`)
  - [x] 인스턴스 resize 시 OverlayFS 마운트 유지 검증 (통합 테스트) — `tests/integration/test_resize_overlay.py`. 19항 참조 (placeholder 제거 + SSH 직접 검증 + FIP 자동 할당)
  - [x] 다중 VM 동시 부팅 시 NFS share 동시 접근 안정성 검증 — `tests/integration/test_concurrent_boot.py`. 19항 참조 (병렬 SSH 마운트 검증)
  - [x] 라이선스/동시 접속 제한 검토 (상용 소프트웨어) — 11.2에서 `union_layers.create_mount` 가드 + 라이선스 필드 구현. 19항에서 DB 통합 회귀 테스트 4건(`test_libraries_license_db.py`) 추가

- [x] 5.5 보안 강화
  - [x] NFS export 옵션 보안: `root_squash`, `sec=sys` vs `sec=krb5` — `_build_nfs_access_metadata` + `create_access_rule(metadata=)` + `ensure_nfs_access_rule(root_squash, sec_flavor)` + 설정값 2개(`manila_nfs_root_squash`, `manila_nfs_sec_flavor`) + 단위테스트 13건
  - [x] CephX 키 로테이션 지원 — `rotate_cephx_access_rule` + `POST /api/instances/{id}/credentials/rotate-cephx` + systemd 타이머
  - [x] VM 간 데이터 격리 검증 (다른 프로젝트의 share 접근 차단) — `union_project_id` 메타 + list/get 필터
  - [x] NFS 방화벽 규칙 자동 관리 (Security Group) — `ensure_union_egress_sg` + instances.py auto-attach

- [x] 5.6 로깅 및 감사
  - [x] 마운트/언마운트 이벤트 로깅 (envmgr-use.sh → `POST /api/union/mounts` Bearer 토큰 통합, best-effort)
  - [x] 라이브러리 사용 통계 (Nova metadata `union_libraries` + `union_user_mounts` 활성 마운트 집계, 10분 시계열 스냅샷)
  - [x] 관리자 대시보드에 라이브러리 사용량 차트 추가 (`LibraryUsageChart.svelte`, 관리자 라이브러리 페이지 상단)

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

## 9. Union Mount 레이어 시스템 v2 (content-addressable)

> 설계 원문: **`union.md`** — 구현 전 반드시 먼저 읽는다.
>
> **핵심 원칙**: content-addressable 불변 레이어 | single-parent 상속(MVP) | Manila 3개 share(RW/RO/manifest) | overlayfs upperdir = 로컬 디스크

### 9.1 Phase 1 — MVP ✅ 코드 완료 (인프라 미설정)

**Manila + CephFS 기반 레이어 스토리지 구성**

- [ ] Manila share 3개 실제 프로비저닝: `layer-store-rw` (Builder RW), `layer-store-ro` (User RO), `manifest-store`
- [ ] Builder VM 설정: LAYER_STORE_RW 마운트, `layerbuild` CLI + 의존성 설치
- [x] `layerbuild` CLI (`scripts/layerbuild.py`):
  - `layerbuild init <name> --version <ver> [--parent <sha256:hash>]` — 작업 디렉토리 생성 + overlay/bind 마운트
  - `layerbuild exec <recipe.sh>` — `systemd-nspawn -D merged/ bash recipe.sh` 격리 실행
  - `layerbuild seal` — 결정적 sha256 계산, `sha256-<hash>/diff/` 이동, 3-lock (chmod+chattr+API seal), API 레이어 등록
  - `layerbuild abort` — 진행 중인 빌드 취소 및 마운트 해제
  - `layerbuild --dry-run <cmd>` — destructive subprocess + API 호출을 트레이스만 출력 (21항)
  - `layerbuild resume-api <sha256:hash>` — seal 시 API 등록 실패한 레이어 재등록 (`.api_pending` 마커, 21항)

**MySQL 8.0 스키마 + Pydantic 모델**

- [x] `backend/app/models/union.py` — Pydantic 모델: `LayerInfo`, `TemplateInfo`, `CreateLayerRequest`, `CreateTemplateRequest`, `AncestorChain`, `SealLayerResponse`
- [x] `backend/app/models/db.py` — ORM: `UnionLayer`, `UnionTemplate`, `UnionUserMount` (SQLAlchemy async)
- [x] `backend/app/database.py` — `CREATE TABLE IF NOT EXISTS union_layers / union_templates / union_user_mounts` DDL (MySQL 8.0+, InnoDB, utf8mb4)
- [x] `backend/app/services/union_layers.py` — 서비스 레이어: CRUD + MySQL `WITH RECURSIVE` CTE 조상 쿼리 + 템플릿 관리

**REST API (Backend)** — `/api/union` 접두어, `backend/app/api/union/`

- [x] `GET /api/union/layers` — 레이어 목록 (페이지네이션, `?name=` 필터)
- [x] `GET /api/union/layers/{id}` — 레이어 상세 조회
- [x] `POST /api/union/layers` — 새 레이어 등록 (sealed=false, 관리자 전용)
- [x] `POST /api/union/layers/{id}/seal` — 레이어 봉인 (관리자 전용, 봉인 후 수정 불가)
- [x] `GET /api/union/layers/{id}/ancestors` — 조상 체인 반환 base-first 순 (lowerdir 조립용)
- [x] `GET /api/union/templates` — 템플릿 목록
- [x] `POST /api/union/templates` — 템플릿 생성 (봉인된 leaf만 허용, 관리자 전용)

**User VM envmgr**

- [x] `scripts/envmgr-init.sh` — cloud-init 통합: CephFS RO share 마운트, envmgr-use 설치, systemd `layer-store-ro.mount` unit 등록
- [x] `scripts/envmgr-use.sh` — 환경 활성화:
  - `envmgr-use <sha256:...>` — leaf 레이어 직접 지정
  - `envmgr-use --template <name>@<ver>` — 템플릿으로 활성화 (API 조회)
  - `envmgr-use --unmount` / `--status`
  - 조상 체인 API 조회 → lowerdir 조립 → upperdir=`/var/overlay/<hash>/upper` (로컬 디스크) → `mount -t overlay /mnt/env`

**테스트**

- [x] `backend/tests/test_union_layers.py` — Layer CRUD(5), Seal(3), ListLayers(2), GetAncestors(3), LayerIdValidation(3), Templates(3), API(11), Dependents(3), DeleteLayer(5), NewAPI(7) = **45개**

### 9.2 Phase 2 — 운영 (목표: Phase 1 완료 후 ~3주)

**Frontend UI**

- [x] `/dashboard/library` 라우트: 레이어 카탈로그 페이지 (트리 시각화)
- [x] `/dashboard/library/create` — 새 레이어 생성 폼 (관리자 전용)
- [x] `/dashboard/library/[id]` — 레이어 상세: 조상 체인, seal 상태, 파생 레이어 목록, seal/삭제 액션
- [x] `/dashboard/library/templates` — 템플릿 관리 UI (목록 + 생성 폼 + 슬라이드 패널 상세)
- [x] VM 생성 wizard — Step 3에 "라이브러리 선택" / "템플릿 선택" 탭 추가 (`SelectTemplate.svelte`)
- [x] Dashboard 사이드바에 "라이브러리" 섹션 추가
- [x] Admin 사이드바에 "라이브러리" 섹션 추가

**보안 + 격리**

- [x] Manila access rule 자동 관리: Builder VM RW 추가/제거 API (`POST /api/union/builder/access`, `DELETE /api/union/builder/access/{id}`)
- [x] 레이어 프로젝트 격리: `project_id` 컬럼 + `list_layers()` 필터링 (NULL=공유, 값=프로젝트 전용, admin=전체)
- [x] seal 후 RW 접근 차단 검증

**운영 도구**

- [x] `GET /api/union/layers/{id}/dependents` — 자식 레이어 목록 (삭제 전 확인용)
- [x] `DELETE /api/union/layers/{id}` — 수동 GC 엔드포인트 (관리자, 자식/템플릿/마운트 참조 있으면 409)
- [x] `GET /api/union/templates/{name}/{version}` — 템플릿 상세 엔드포인트 (resolved_stack 포함)
- [x] 레이어 크기 집계: `GET /api/union/stats/storage` — `size_bytes`/`file_count` SQL SUM 집계 (`total_layers`, `sealed_layers`, `total_size_bytes`, `total_file_count`)
- [x] 마운트 API: `POST /api/union/mounts` (기록), `POST /api/union/mounts/{id}/unmount` (해제), `sealed_at` 봉인 타임스탬프 추가

**테스트 확장**

- [x] Integration test: Builder VM → seal → User VM mount 전체 플로우 — `tests/integration/test_union_e2e.py` (19항). create→seal→fork→template→record_mount→409 가드→unmount→cleanup 13단계 검증
- [x] 삭제 차단 동작 검증 (자식/템플릿/활성 마운트 — 단위 테스트 포함)

### 9.3 Phase 3 — 확장 (목표: Phase 2 완료 후)

- [x] **Fork 지원**: `POST /api/union/layers/{id}/fork` — sealed 레이어에서 새 RW 레이어 파생
- [x] **Rebuild**: 동일 부모 + 다른 내용 → 새 hash 신규 레이어 (overwrite 금지 정책 유지)
- [x] **멀티 상속(실험)**: lowerdir에 여러 부모 지원 — 다이아몬드 충돌 해결 정책 필요. 22항 참조 (백엔드 API + DB + 서비스 레이어 도입, layerbuild CLI/envmgr 확장은 별도 작업)
- [x] **OverlayFS 상태 모니터링 에이전트**: User VM에서 마운트 상태 주기적 보고
- [x] **Manila Share Snapshot 관리**: 레이어 백업/복원

---

## 10. 관리자 UX 개선 (2026-04-27)

### 10.1 관리자 페이지 필터/검색 추가 (volumes, instances, topology)

> **목표**: 관리자 페이지에서 리소스가 많을 때 특정 항목을 빠르게 찾을 수 있는 서버사이드 필터 추가

- [x] `backend/app/api/identity/admin.py` — `list_all_volumes`: `project_id`, `status`, `name` 쿼리 파라미터 추가 (Cinder `name~` substring 매칭)
- [x] `backend/app/api/identity/admin.py` — `list_all_instances`: `status`, `name` 쿼리 파라미터 추가 (Nova `name=.*{re.escape(input)}.*` regex 변환)
- [x] `backend/app/api/identity/admin.py` — `admin_topology`: `TopologyInstance` 빌드 시 `project_id` 포함
- [x] `backend/app/models/storage.py` — `TopologyInstance.project_id: str | None = None` 추가
- [x] `backend/tests/test_admin_filters.py` — **신규** 7개 테스트: volumes(status/project_id/name~), instances(status/name regex/metachar escape), topology(project_id 포함 검증)
- [x] `frontend/src/lib/components/GlobalTopology.svelte` — `TopologyInstance.project_id` 인터페이스 추가 + `projectId` prop 기반 인스턴스 필터링
- [x] `frontend/src/routes/admin/volumes/+page.svelte` — 프로젝트 autocomplete / 상태 select / 이름 검색 필터 UI (서버사이드, 페이지네이션 연동)
- [x] `frontend/src/routes/admin/instances/+page.svelte` — 상태/이름 필터 추가, 기존 클라이언트사이드 프로젝트 필터 → 서버사이드 전환 (`filteredInstances` derived 제거)
- [x] `frontend/src/routes/admin/topology/+page.svelte` — 프로젝트 검색 드롭다운 추가, `GlobalTopology`에 `projectId`/`showAll` props 연결

### 10.2 전체 페이지 자동 새로고침 추가 (기본 ON)

> **목표**: 새로고침 버튼이 있는 모든 페이지/패널에 자동 새로고침 추가. 기본 ON, localStorage 영속, 탭 비활성 시 일시정지, 페이지 성격별 차등 주기

- [x] `frontend/src/lib/utils/autoRefresh.svelte.ts` — **신규**. Svelte 5 rune 기반 hook. `createAutoRefresh(fn, options)`:
  - localStorage에 `autoRefresh.<key>.active` / `autoRefresh.<key>.interval` 영속
  - Page Visibility API: `document.hidden` 시 timer 정지, 탭 복귀 시 즉시 1회 fetch + 재시작
  - `$effect` cleanup으로 timer/listener 자동 해제 (SSR 안전)
- [x] `frontend/src/lib/components/AutoRefreshControl.svelte` — **신규**. 토글 버튼 + 주기 select + 수동 새로고침 버튼 통합 컴포넌트. `PageHeader` actions snippet에 삽입.
- [x] **admin 23개 페이지 적용**:
  - 15s: `instances`, `monitoring`, `services`, `database-instances`, `drover`, `containers`, `object-storage/[name]`
  - 30s: `topology`, `floating-ips`, `routers`, `gpu`, `hypervisors`, `ports`, `networks`, `file-storage`, `volumes`, `images`, `object-storage`
  - 60s: `flavors`, `groups`, `users`, `roles`, `projects`
- [x] **dashboard 5개 페이지 적용**:
  - 10s: `containers/clusters/[id]`
  - 15s: `containers/instances/[id]` (로그 패널)
  - 30s: `topology`, `file-storage/manage`, `object-storage/buckets/[name]`
- [x] `frontend/src/lib/components/InstanceDetailPanel.svelte` — 콘솔 로그 ad-hoc `setInterval` → `createAutoRefresh` 마이그레이션 (15s)
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — 이벤트 ad-hoc `setInterval` → `createAutoRefresh` 마이그레이션 (15s)
- [x] 기존 ad-hoc 자동새로고침 3곳 통합 제거: `admin/services` (`$effect`+setInterval), `dashboard/containers/clusters/[id]` (자체 setInterval+toggleAutoRefresh), `dashboard/file-storage/manage` (AutoRefreshToggle+setInterval)
- [x] 자동 새로고침 fn은 **필터/marker 보존** (현재 페이지 유지), 수동 새로고침은 **기존 필터 리셋** 동작 유지 (의도적 분리)

### 10.3 관리자 볼륨 — 상태 변경 + 명시적 강제삭제 (2026-04-27)

> **목표**: `deleting` / `error_*` 등 비정상 상태 볼륨을 admin이 임의 상태로 전환하거나 명시적으로 강제 삭제할 수 있도록 UI/API 확장

- [x] `backend/app/api/identity/admin.py::delete_volume` — `_ERROR_STATUSES` (`error/deleting/error_*`) 자동 폴백: `reset_status` → 일반 `delete` → `os-force_delete` 3단계 시퀀스
- [x] `backend/app/api/identity/admin.py::force_delete_admin_volume` — **신규** `POST /api/admin/volumes/{id}/force-delete` (status 무관, attached 볼륨은 409)
- [x] `backend/tests/test_admin_volume_delete.py` — **신규** 11개 (자동 폴백 7 + force-delete 4: normal_status, attached_409, already_gone_204, requires_admin_403)
- [x] `frontend/src/routes/admin/volumes/+page.svelte` — `상태초기화` (error 한정) → `상태변경` (모든 볼륨 노출), `error*/deleting` 상태에 한해 `강제삭제` 버튼/rose 경고 모달 추가

---

## 11. VM 스케일링 + 보안 강화 (5.4 + 5.5 완성) — Milestone 11 ✅

> **완료**: resize 엔드투엔드(11.1), OverlayFS 검증 + 라이선스 가드(11.2), NFS 강화 + CephX 회전 + 3-share wiring(11.3), 프로젝트 격리 + Union SG 자동화(11.4) 전 항목 완료.

> **목표**: 미완료 상태로 남은 5.4(VM 스케일링) + 5.5(보안 강화) 항목을 4주 로드맵으로 완성

### 11.1 인스턴스 resize 엔드투엔드 (Week 1)

- [x] `backend/app/services/nova.py` — `resize_server()`, `revert_resize_server()` 추가
- [x] `backend/app/api/identity/admin.py` — `POST /api/admin/instances/{id}/resize`, `/revert-resize` 엔드포인트 추가 (관리자 전용, 캐시 무효화 포함)
- [x] `frontend/src/lib/components/InstanceDetailPanel.svelte` — ACTIVE/SHUTOFF 상태에서 "리사이즈" 버튼 + flavor select 모달, VERIFY_RESIZE 상태에서 "되돌리기" 버튼 추가
- [x] `backend/tests/test_admin_resize.py` — 신규 4건 (resize/revert 성공, 403 비관리자, nova 오류 400)

### 11.2 resize OverlayFS 검증 + 다중 VM 동시 부팅 + 라이선스 가드 (Week 2)

- [x] `backend/app/templates/overlay_setup.sh.j2` — jittered backoff (`RANDOM % 3`) 추가
- [x] `backend/tests/integration/test_concurrent_boot.py` — N=5 VM 동시 생성 → OverlayFS 마운트 검증 (slow marker, 실 인프라 skip)
- [x] `backend/tests/integration/test_resize_overlay.py` — resize → confirm → mountpoint 검증 (slow marker, 실 인프라 skip)
- [x] `backend/app/models/storage.py` + `db.py` — `LibraryConfig.license_type`, `max_concurrent_mounts` 필드 추가
- [x] `backend/app/services/union_layers.py:create_mount` — mount 한도 초과 시 409 가드
- [x] `backend/app/api/union/layers.py` — 두 필드 라우터 노출
- [x] `frontend/src/routes/admin/libraries/+page.svelte` — 라이선스 배지 + 활성 마운트 수 표시
- [x] `backend/tests/test_libraries.py` — license/max_concurrent_mounts 직렬화 단위 테스트 3건

### 11.3 NFS 옵션 강화 + CephX 회전 + 3-share wiring (Week 3)

- [x] `backend/app/api/compute/instances.py:1086` + `overlay_setup.sh.j2:28` — `nosuid,nodev,noexec` 추가
- [x] `scripts/envmgr-init.sh` — RO mount 옵션 통일 (`ro,nosuid,nodev,noexec,_netdev,noatime`)
- [x] `instances.py:1063` — `0.0.0.0/0` 폴백 제거 → vm_ip 미확보 시 503
- [x] `backend/app/services/manila.py` — `rotate_cephx_access_rule()` 헬퍼
- [x] `backend/app/api/compute/instance_health.py` — `POST /api/instances/{id}/credentials/rotate-cephx` 추가 (Bearer 토큰 인증)
- [x] `scripts/envmgr-rotate-key.sh` + systemd `union-rotate-key.timer` (신규, cloudinit_base.yaml.j2 통해 주입)
  - [x] **버그 수정**: `write_files`에 스크립트 미주입 → `envmgr_rotate_key.sh.j2` 템플릿 추가 + `cloudinit.py` 렌더링 + `cloudinit_base.yaml.j2` 주입 완료
- [x] `backend/app/api/union/layers.py` — `POST /api/union/user/access`, `DELETE /api/union/user/access/{access_id}` (3-share user wiring)
- [x] `backend/app/services/cloudinit.py` — `union_ro_share_export` 파라미터 + write_files 주입 (`LAYER_STORE_RO_EXPORT`)
- [x] `backend/app/config.py` — `union_cephx_rotate_hours: int = 24` 추가
- [x] `backend/tests/test_manila_rotate.py` — `rotate_cephx_access_rule` 단위 테스트 3건
- [x] `backend/tests/test_cloudinit.py` — `nosuid,nodev,noexec` + `LAYER_STORE_RO_EXPORT` 단위 테스트 2건 + rotate-key 주입 테스트 4건
- [x] `backend/tests/test_endpoint_inventory.py` — rotate-cephx 엔드포인트 whitelist 추가

### 11.4 격리 검증 + SG 자동화 (Week 4) ✅

- [x] `backend/app/services/manila.py` — `_parse_file_storage` `is_public` 추출, `list_file_storages` `caller_project_id` 필터 추가
- [x] `backend/app/models/storage.py` — `FileStorageInfo.is_public` 필드 추가
- [x] `backend/app/api/compute/instances.py:_prepare_dynamic_file_storage` — `union_project_id` 메타 자동 주입
- [x] `backend/app/services/library_builder.py` — prebuilt 빌드 완료 후 `set_share_public(True)` 자동 호출
- [x] `backend/app/api/storage/file_storage.py` — non-admin list `caller_project_id` 전달, GET cross-project private → 404
- [x] `backend/tests/integration/test_isolation.py` — 신규 3건 (`@pytest.mark.slow`, 실 인프라 skip 스켈레톤)
- [x] `backend/app/services/neutron.py` — `ensure_union_egress_sg()` idempotent 헬퍼 (NFS/CephFS/HTTP(S) 6 rule)
- [x] `backend/app/config.py` — `union_auto_egress_sg_enabled`, `union_egress_sg_name` 설정값 추가
- [x] `backend/app/api/compute/instances.py:create_instance` + `create_instance_async` — Union 사용 시 SG 자동 attach
- [x] `backend/tests/test_file_storage.py` — 격리 테스트 4건 (list 필터, public 노출, cross-project 404, admin 허용)
- [x] `backend/tests/test_manila_isolation.py` — `list_file_storages` caller_project_id 필터 단위 2건
- [x] `backend/tests/test_neutron.py` — `ensure_union_egress_sg` 3건 (미존재 생성+6룰, idempotent, 누락 룰만 추가)
- [x] `backend/tests/test_instances.py` — Union SG 자동 attach 2건 (auto-attach, disabled 시 미호출)


## 11.5 테스트 인프라 강화 — Phase A (mock 트로이 목마 → 실 검증 전환)

- [x] `backend/pyproject.toml` — pytest markers 4개(slow/db/redis/crypto) + `fakeredis[lua]>=2.21` dev 의존성 추가
- [x] `backend/tests/test_k3s_crypto.py` — AES-256-GCM 18케이스 신규 (0% → ≥95% 라인 커버)
- [x] `backend/tests/test_k3s_kube.py` — 4단 nested patch 제거 → `assert_called_once_with(url, headers=...)` URL 검증
- [x] `backend/tests/test_dashboard.py` — `patch("...asyncio")` 제거, `cached_call` side_effect 리스트로 대체, `status_code == 200` 단정
- [x] `backend/tests/test_loadbalancers.py` — 모든 success 케이스에 `assert_called_once_with(...)` 인자 검증 추가
- [x] `backend/tests/test_admin_libraries.py` — `cancel_build` mock `assert_called_once_with(conn, build_id)` 강화
- [x] `backend/tests/test_admin_endpoints.py` — 432줄 트로이 목마 전수 삭제 (`test_endpoint_inventory.py`의 메타 검증과 100% 중복 확인)

## 11.5 테스트 인프라 강화 — Phase B (동어반복 정리)

- [x] `backend/tests/test_union_layers.py` — `patch.object(svc, fn)` 후 fn 재호출 동어반복 2건 삭제 (DB 통합으로 이전)
- [x] `backend/tests/test_k3s_callback.py` — `assert_called_once_with(exact, args)` 강화 (failure/success 시나리오 인자 고정)

## 11.5 테스트 인프라 강화 — Phase C (MariaDB 실 SQL 통합)

- [x] `docker-compose.yml` — `profiles: ["test"]` MariaDB 11.4 서비스 추가
- [x] `backend/tests/fixtures/__init__.py` — 신규 (fixtures 패키지)
- [x] `backend/tests/test_union_layers_db.py` — 20케이스: INSERT/CTE/FK/격리/mount 실 SQL 검증 (`@pytest.mark.db`)
- [x] `.github/workflows/test.yml` — `test-backend-db` 잡 신규 (dev 브랜치 push 전용, MariaDB 11.4 서비스)

## 11.5 테스트 인프라 강화 — Phase D (실 OpenStack 통합 테스트 활성화)

- [x] `backend/tests/integration/credentials.py` — `project_b_credentials()` 함수 추가
- [x] `backend/tests/integration/conftest.py` — `project_b_credentials_fx`, `project_b_auth_data`, `project_b_client` 픽스처 추가
- [x] `backend/tests/integration/test_isolation.py` — pytest.skip 제거, 3건 본문 구현 (dynamic 격리, public 노출, 직접 GET 404)
- [x] `backend/tests/integration/test_concurrent_boot.py` — pytest.skip 제거, env var `AFTERGLOW_TEST_CONCURRENT_VMS` 지원, timeout 15분
- [x] `backend/tests/integration/test_resize_overlay.py` — pytest.skip 제거
- [x] `.github/workflows/test.yml` — `test-backend-integration` 잡에 project_b secrets 추가, `-m slow` 마커 적용


## 관리자 인스턴스 자격 증명 관리

### 런타임 패스워드 재설정 (QEMU Guest Agent 기반)

- [x] `backend/app/services/nova.py` — `change_server_password(conn, server_id, password)`: Nova `changePassword` action 호출 (libvirt+QGA 게스트 비밀번호 변경)
- [x] `backend/app/services/nova.py` — `get_server_image_meta(conn, server_id)`: 이미지 QGA 지원 여부(`hw_qemu_guest_agent`) + `os_admin_user` 메타 조회. 볼륨 부팅 인스턴스는 cinder `volume_image_metadata` fallback
- [x] `backend/app/models/compute.py` — `AdminPasswordRequest`, `AdminPasswordPrecheck` Pydantic 모델 추가
- [x] `backend/app/api/compute/instances.py` — `GET /{server_id}/admin-password/precheck` (관리자 전용, QGA/상태 사전 점검)
- [x] `backend/app/api/compute/instances.py` — `POST /{server_id}/admin-password` (관리자 전용, ACTIVE + QGA 검증 후 변경, audit 로그 출력)
- [x] `backend/tests/test_instance_password.py` — 9케이스 단위 테스트 (403/404/409/422/204 검증)
- [x] `frontend/src/lib/components/InstanceDetailPanel.svelte` — admin-only "비밀번호 재설정" 버튼 + precheck 자동 호출 + 인라인 모달 (QGA 경고, os_admin_user 표시)

### 런타임 SSH 키 주입 정책

- [x] 표준 OpenStack은 실행 중 SSH 키 주입을 미지원 — 정책상 런타임 주입 기능 미구현
- [x] `InstanceDetailPanel.svelte` 패스워드 모달 내에 SSH 키 안내 문구 + 키페어 관리 링크 + rebuild 안내 추가

### GPU 인스턴스 DCGM Exporter 자동 설치 (cloud-init)

- [x] `backend/app/templates/cloudinit_base.yaml.j2` — `gpu_available=true` 시 설치 스크립트 + systemd unit 자동 생성 (네이티브 바이너리, `0.0.0.0:9400`)
- [x] `backend/app/services/cloudinit.py` — `_DCGM_EXPORTER_VERSION` 핀 상수 추가, 템플릿 렌더에 버전 전달
- [x] `backend/tests/test_cloudinit.py` — GPU/non-GPU 분기 3케이스 추가
- [x] **GPU 스택 풀-스택 idempotent 설치** (베이스 이미지 무관): `install_dcgm_exporter.sh` 에 ① `nvidia-smi` 미발견 시 `ubuntu-drivers autoinstall`, ② `nvidia-dcgm.service` 미발견 시 CUDA repo (`cuda-keyring`) 등록 + `datacenter-gpu-manager` 설치, ③ dcgm-exporter 바이너리 다운로드 단계 추가. `dcgm-exporter.service` 의 `Requires=nvidia-dcgm.service` 추가로 데몬 부팅 후 exporter 기동 보장. `test_cloudinit.py` 에 드라이버/DCGM 데몬 자동 설치 + systemd 의존성 검증 2건 추가
- [→] 보안 그룹 9400/tcp 자동 허용 — 12.2에서 통합 처리
- [→] Prometheus 스크래핑 대상 자동 등록 — 12.3/12.4에서 통합 처리


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

## 13. 오브젝트 스토리지 5GB+ 대용량 업로드 (Swift SLO)

### 13.1 문제

기존 업로드는 5GB 하드 캡으로 인해 대용량 파일(5GB 초과)을 버킷에 올릴 수 없었다:
- Traefik middleware `maxRequestBodyBytes: 5GB`
- 백엔드 `_MAX_UPLOAD_BYTES = 5GB` + 413 응답
- Swift 단일 PUT 프로토콜 한도 5GB

### 13.2 구현

- [x] `backend/app/services/swift.py` — `_SLO_SEGMENT_SIZE = 1 GiB`; `upload_object` 1 GiB 초과 시 수동 SLO: `_LimitedReader`로 1 GiB씩 `proxy.put()` 루프 → `?multipart-manifest=put` manifest PUT (openstacksdk file-like SLO 버그 우회)
- [x] `backend/app/services/swift.py` — `delete_object` SLO `?multipart-manifest=delete` 정리 (quota 누수 방지)
- [x] `backend/app/api/object_storage/containers.py` — streaming PUT endpoint + `HttpException` 에러 디테일 응답 노출
- [x] `backend/app/config.py` — `os_swift_upload_timeout` 기본값 600 → 1800 (30분)
- [x] `deploy/k8s-template/middleware.yaml` — Traefik buffering 제거 → streaming pass-through
- [x] `backend/tests/test_object_storage.py` — 수동 SLO 루프 검증 테스트 업데이트 (3건)
- [x] `frontend/src/lib/stores/uploadQueue.ts` — 백그라운드 업로드 큐 store
- [x] `frontend/src/lib/components/UploadDock.svelte` — 우하단 업로드 진행 도크 위젯
- [x] `frontend/src/lib/components/UploadModal.svelte` — enqueue+즉시 닫기로 단순화 (진행 UI → Dock)
- [x] `frontend/src/routes/+layout.svelte` — UploadDock 글로벌 마운트
- [x] `frontend/src/routes/dashboard/object-storage/buckets/[name]/+page.svelte` — silent 자동새로고침 + keyed each + DnD 업로드
- [x] `frontend/src/routes/admin/object-storage/[name]/+page.svelte` — 동일 패턴 적용

### 13.3 검증 (사용자 직접)

- [ ] Ceph RGW 9.58 GB 파일 업로드 → 200 응답 + `{container}_segments` 에 10개 세그먼트 확인
- [ ] 다운로드 후 md5 일치
- [ ] 자동새로고침 15초 폴링 중 표 깜빡임 없음
- [ ] DnD로 파일 드롭 → Dock에 진행 표시
- [ ] 업로드 중 다른 페이지 이동 → Dock 유지, 완료 후 목록 자동 갱신

## 14. 오브젝트 스토리지 대용량 다운로드 + 라이트 모드 색상

### 14.1 문제

- 9.5GB 파일 다운로드 시 `AbortError: The user aborted a request` (5분 fetch timeout + 메모리 blob 적재)
- 한글 파일명 다운로드 시 `IT%E1%84...zip`으로 깨지는 문제
- 버킷 선택 액션바·이동/삭제 버튼이 라이트 모드에서 흐릿/저가독

### 14.2 구현

- [x] `backend/app/api/object_storage/containers.py` — `_make_content_disposition()` 헬퍼 추가 (RFC 5987 `filename*=UTF-8''...` 형식)
- [x] `backend/app/api/object_storage/containers.py` — `POST /{container}/objects/{object:path}/download-token` 신규 엔드포인트 (Redis 단발 토큰, TTL 60초, 1회 사용 강제)
- [x] `backend/app/api/object_storage/containers.py` — `download_object` 토큰 쿼리 파라미터 분기 추가 (헤더 인증 경로 유지)
- [x] `backend/app/api/object_storage/containers.py` — `preview_object` Content-Disposition RFC 5987 적용
- [x] `backend/tests/test_object_storage.py` — Content-Disposition 포맷·토큰 발급·만료·불일치·유효 다운로드 테스트 추가
- [x] `frontend/src/routes/dashboard/object-storage/buckets/[name]/+page.svelte` — `downloadObject()` 단발 토큰 발급 후 브라우저 네이티브 다운로더 트리거로 재작성
- [x] `frontend/src/routes/layout.css` — 인디고 액션바·버튼, 레드 삭제 버튼 `:root.light` 오버라이드 추가

### 14.3 검증 (사용자 직접)

- [ ] 9.5 GB 파일 다운로드 → `AbortError` 없이 브라우저 다운로드 패널에서 진행
- [ ] 한글 파일명("한글 2024.zip" 등) 다운로드 → 저장 파일명 정상
- [ ] 토큰 재사용 시도 → 403
- [ ] 라이트 모드 버킷 상세 → 선택 행·액션바·버튼 색상 가독성 확인

## 15. UI/Design — Afterglow 브랜드 리디자인

### 15.1 진행 현황

- [x] Phase 1: `@theme` 토큰 블록, Geist 폰트, `RingMark.svelte` 컴포넌트화
- [x] Phase 2: `statusColors.ts` → 5 semantic tone 재작성, `StatusChip.svelte` dot pulse
- [x] Phase 3: 사이드바 active warm soft + 좌측 strip, `StatTile`/`QuotaBar` accent 토큰화
- [x] Phase 3.5: 라이트 모드 warm WCAG AA 보정 (orange-600/700 오버라이드)
- [x] Phase 6a: `--gradient-brand/warm`, `--glow-warm/accent` 토큰, `GradientText.svelte`, VM 생성 버튼 warm gradient
- [x] Phase 6b: `StatTile` 아이콘 칩 radial halo + glow
- [x] Phase 6c: 위저드 스테퍼 warm gradient (완료/현재 step 원 + connector)
- [x] Phase 6d: `Toast` actionable 링크 (`action?: { label, onClick }`) + 토큰 기반 색상
- [x] Phase 6e: `EmptyState.svelte` warm halo 신규 컴포넌트
- [x] Phase 6f: `Card.svelte` 좌상단 radial warm highlight
- [x] Phase 7: `Button.svelte` variant 컴포넌트 (primary/secondary/ghost/danger × sm/md/lg), primary CTA 15곳 warm gradient 통일
- [x] Phase 5a: `DetailHeader.svelte` 상세 페이지 헤더 통일 (Instance/K3s/LB/Router/Volume/FileStorage 6종)
- [x] Phase 5d: Cmd-K 팔레트 (`nav.ts` 추출, `palette.ts` store, `CmdPalette.svelte`, 상단바 ⌘K 트리거)
- [x] Phase 5e: 대시보드 `TopologyCard.svelte` wrapper 임베드 (GlobalTopology 무변경)
- [ ] Phase 4: `layout.css` override sheet 제거 (336 → ~70 라인)

### 15.2 검증 (사용자 직접)

- [ ] 다크모드: 대시보드 username warm gradient 텍스트, 사이드바 VM 생성 버튼 warm gradient glow
- [ ] 라이트모드: 사이드바 active 항목이 진한 오렌지 텍스트 + 좌측 strip 명확히 보임
- [ ] 다크/라이트 토글 시 사이드바 active 자연스럽게 전환
- [ ] 인스턴스/볼륨 페이지 StatusChip BUILD/CREATING 상태 dot pulse 동작
- [ ] VM 생성 위저드 스테퍼 완료/현재 step warm gradient 적용 확인
- [ ] ⌘K 팔레트: 라우트 jump + 리소스 검색 fuzzy match + 상단바 버튼 트리거 동작 확인
- [ ] 인스턴스/K3s/LB/Router/Volume/FileStorage 상세 헤더 `DetailHeader` 통일 확인
- [ ] 대시보드 하단 네트워크 토폴로지 카드 노출 + 전체보기 링크 동작

## 16. Activity Log

- [x] Phase A: TopologyCard fitWidth 버그 수정 (`{@const}` → `$derived`)
- [x] Phase B: backend activity_logs 테이블 + 모델 + 서비스 + 라우터 (008 마이그레이션)
- [x] Phase C: 6개 도메인 mutation 라우터에 rec() 활동 로그 통합
- [x] Phase D: frontend apiMut 헬퍼 + 6개 핵심 mutation 사이트 toast 마이그
- [x] Phase E: admin 프로젝트 상세 라우트 + ActivityLogTable 컴포넌트
- [x] Phase F: account ActivitySection (본인 활동 조회)


## 17. 인스턴스 성능 모니터링

- [x] Phase 1: Prometheus http_sd 설정 + sd_targets.py 9100/9400 분리 (node_exporter / dcgm_exporter)
- [x] Phase 2: PromQL 프록시 엔드포인트 신설 (`GET /api/instances/{id}/metrics`) + project_id 권한 검증
- [x] Phase 3: InstanceDetailPanel MetricsPanel 카드 + 4종 차트 (GPU VM: +2 차트)
- [x] Phase 4: `/metrics-batch` 단일 엔드포인트 + httpx 커넥션 풀 + `calc_step` 최적화 (다중 차트 API 호출 1→1 통합)

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

## 19. 통합 테스트 보강 (2026-05-10) — 5.4 + 9.2 마지막 미완료 항목 마감

> **배경**: 11.5 Phase D에서 통합 테스트 스켈레톤은 `pytest.skip` 제거 단계까지 진행됐으나, 본문이 `image_id="placeholder"` / `flavor_id="placeholder"` 더미 값으로 작성되어 실 OpenStack 셀프호스티드 러너에서도 401/404로 즉시 실패. OverlayFS 마운트 검증도 health endpoint의 `mount_ok` 한 비트에만 의존해 agent 거짓 보고를 잡지 못함. 9.2 Builder→User VM 통합 테스트는 부재.

### 19.1 DELETE 템플릿 엔드포인트 + 서비스 함수 신규

- [x] `backend/app/services/union_layers.py` — `delete_template(session, name, version)` 추가 (멱등, 미존재 시 False)
- [x] `backend/app/api/union/layers.py` — `DELETE /api/union/templates/{name}/{version}` 관리자 전용 라우터 추가 (404 분기 + activity log)
- [x] `backend/tests/test_union_layers.py` — 단위 테스트 4건 (admin 정상 204 / 404 / 비관리자 403 / 서비스 멱등 False)

### 19.2 SSH 검증 헬퍼

- [x] `backend/tests/integration/ssh_helper.py` — 신규. `wait_for_ssh`, `ssh_run`, `verify_overlay_mount`, `verify_nfs_mounts`, `verify_envmgr_status`. subprocess(ssh) 기반(paramiko 미도입), `BatchMode=yes` + `StrictHostKeyChecking=no` + `UserKnownHostsFile=/dev/null` 공통 옵션

### 19.3 통합 테스트 본문 정합성 (5.4)

- [x] `backend/tests/integration/conftest.py` — `IntegrationResources` dataclass + `integration_resources` 픽스처 추가 (env 기반, 누락 시 자동 skip, SSH 키 chmod 600 자동)
- [x] `backend/tests/integration/test_resize_overlay.py` — placeholder 제거, FIP 자동 할당, SSH로 사전·사후 OverlayFS 검증 (12단계)
- [x] `backend/tests/integration/test_concurrent_boot.py` — placeholder 제거, FIP 동시 할당, 병렬 SSH 마운트 검증, health 이중 검증

### 19.4 Union v2 엔드투엔드 통합 테스트 (9.2)

- [x] `backend/tests/integration/test_union_e2e.py` — Builder→seal→fork→template→user mount→409 가드→unmount→cleanup 13단계. manila + RW/RO share 미설정 환경에서는 builder/user access 단계만 조건부 skip하고 핵심 흐름은 항상 검증

### 19.5 라이선스/동시 마운트 가드 회귀 테스트 (5.4)

- [x] `backend/tests/test_libraries_license_db.py` — 신규 4건 (`@pytest.mark.db`):
  - `commercial + max=2` → 첫 두 mount 성공, 세 번째 409
  - unmount 후 슬롯 회수 → 새 mount 성공
  - `open + max=NULL` → 10건 동시 mount 무제한
  - `commercial + max=0` → 모든 mount 즉시 409
- 11.5 Phase C MariaDB 11.4 인프라 재사용. `test_union_layers_db.py`와 동일 fixture 패턴

### 19.6 CI workflow 통합

- [x] `.github/workflows/test.yml::test-backend-integration` — 6개 신규 env 노출:
  - `AFTERGLOW_TEST_IMAGE_ID`, `AFTERGLOW_TEST_FLAVOR_SMALL`, `AFTERGLOW_TEST_FLAVOR_MEDIUM` (secrets)
  - `AFTERGLOW_TEST_SSH_KEY` (secrets)
  - `AFTERGLOW_TEST_LIBRARY_IDS`, `AFTERGLOW_TEST_SSH_USER` (vars)
- secrets/vars 미설정 시 픽스처에서 자동 skip → CI 차단 없음. 등록은 GitHub UI에서 별도 작업

### 19.7 검증 요약

```bash
# 로컬 단위 (즉시 검증 가능)
cd backend && uv run pytest tests/test_union_layers.py -v -k "delete_template"  # 4 passed

# DB 통합 (MariaDB profile=test 컨테이너 필요)
docker compose --profile test up -d mariadb
AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://... uv run pytest tests/test_libraries_license_db.py -m db

# 실 인프라 (셀프호스티드 러너 — 사용자 환경에서 1회 검증)
AFTERGLOW_ALLOW_INSECURE=1 AFTERGLOW_TEST_IMAGE_ID=<uuid> ... \
  uv run pytest tests/integration/test_resize_overlay.py tests/integration/test_concurrent_boot.py tests/integration/test_union_e2e.py -m slow
```

## 20. K3s 부팅 데드락 해소 — Barbican KMS / Keystone Auth host static pod 전환 (2026-05-10) — 8.14 후속 마감

> **배경**: 8.14에서 두 K3s 보안 플러그인이 부팅 데드락으로 강제 비활성화되어 있었다. Barbican KMS는 DaemonSet으로 동작해 apiserver 위에 놓여 KMS socket이 부팅 시 없어 chicken-and-egg, Keystone Auth는 cluster service URL을 webhook endpoint로 사용해 부팅 직후 DNS resolve 실패. 두 플러그인 모두 **host static pod**(`/var/lib/rancher/k3s/agent/pod-manifests/`)로 재구조화 — kubelet이 apiserver 의존 없이 직접 띄우므로 의존 역전 해소.

### 20.1 Barbican KMS — host static pod 전환

- [x] `backend/app/templates/k3s_plugins/barbican_kms/static_pod.yaml.j2` 신규 — kind=Pod, hostNetwork=true, priorityClassName=system-node-critical, hostPath /var/lib/kms (socket) + /etc/kubernetes/barbican-cloud.conf (cloud-config), securityContext.privileged=true
- [x] `backend/app/templates/k3s_plugins/barbican_kms/cloud_conf.yaml.j2` 신규 — [Global] + [KeyManager] 섹션. Secret 의존 제거, host file 0600. **보안 trade-off**: 기존 Secret(=etcd, KMS 미작동 시 plaintext)과 동등한 plaintext-at-rest posture, 위치만 다름 (의도적)
- [x] `backend/app/services/k3s_plugins/barbican_kms.py` 재작성:
  - `should_deploy()` 강제 False 제거 → `enabled + KEK + 자격증명` 검증
  - `extra_write_files()` 3건 (encryption-config.yaml, static pod manifest, barbican-cloud.conf) 모두 0600
  - `generate_manifests()` 빈 문자열 반환 (DaemonSet 제거)
  - `server_install_args()` 에 `--kubelet-arg=pod-manifest-path=/var/lib/rancher/k3s/agent/pod-manifests` 추가

### 20.2 Keystone Auth — hostNetwork host static pod 전환

- [x] `backend/app/templates/k3s_plugins/keystone_auth/static_pod.yaml.j2` 신규 — hostNetwork=true, `--listen=127.0.0.1:8443`, `--keystone-policy-file=/etc/policy/policy.json` (upstream 정확한 플래그명, PolicyFile은 PolicyConfigMap보다 우선이라 ConfigMap 의존 완전 제거)
- [x] `backend/app/templates/k3s_plugins/keystone_auth/webhook_config.yaml.j2` — endpoint `https://k8s-keystone-auth.kube-system.svc.cluster.local:8443/webhook` → `https://127.0.0.1:8443/webhook`
- [x] `backend/app/services/k3s_plugins/keystone_auth.py` 재작성:
  - `should_deploy()` 강제 False 제거 → `enabled + image + os_auth_url` 검증
  - `extra_write_files()` 5건 (webhook config, static pod manifest, tls.crt, tls.key, policy.json)
  - `generate_manifests()` 빈 문자열 반환 (Deployment/Service/RBAC 제거)
  - `server_install_args()` 에 `--kubelet-arg=pod-manifest-path=...` 추가 (Barbican과 동일, `aggregate_server_args` dedup으로 자동 처리)
  - `_get_or_create_cert` 캐싱은 그대로 유지 (extra_write_files에서도 같은 cert/key 사용)

### 20.3 단위 테스트

- [x] `backend/tests/test_k3s_plugins.py` — 게이팅 테스트 정상 분기로 재작성 + 신규 11건:
  - **Barbican (5건 + 1)**: should_deploy_when_enabled_and_kek_set, server_install_args_includes_kubelet_arg, extra_write_files_paths_and_modes, static_pod_manifest_valid_pod, generate_manifests_empty, arg_path_matches_write_file
  - **Keystone (6건)**: should_deploy_when_enabled, should_not_deploy_without_image, server_install_args_includes_kubelet_arg, extra_write_files_paths, webhook_endpoint_is_localhost, static_pod_listens_on_localhost, generate_manifests_empty
- [x] `backend/tests/test_k3s_clusters.py` — 8.14 게이팅 4건 (강제 False 검증) → 정상 분기 검증 (`should_deploy=True` when 설정 충족)으로 재작성
- [x] `_base_settings()` / `_make_plugin_settings()` 에 `os_project_name`, `os_project_domain_name`, `k3s_keystone_auth_image`, `k3s_barbican_kms_image` 보강

### 20.4 부팅 race 가정 명시

apiserver와 kubelet은 K3s 안에서 동일 `k3s server` 프로세스의 자식이라 거의 동시 시작. apiserver의 KMS provider 초기화는 **`PluginInitTimeout`(최근 K8s 기본 60초)** 동안 socket 연결 retry → kubelet이 static pod를 띄워 KMS socket 생성하는 수초~십수 초 윈도우를 흡수. 향후 K8s가 timeout을 단축하면 추가 방어(`ExecStartPre` socket-wait) 필요. Keystone webhook은 lazy 연결이라 race 부담 없음.

### 20.5 실 환경 검증 (사용자 1회)

1. `config.toml` 에 `[k3s] barbican_kms_enabled=true`, `barbican_kms_kek_id=<id>`, `keystone_auth_enabled=true` 활성화
2. 새 K3s 클러스터 생성 → 부팅 데드락 없이 ACTIVE 도달
3. `kubectl get pods -n kube-system` → barbican-kms / k8s-keystone-auth Running
4. `kubectl create secret generic test --from-literal=foo=bar` → etcd raw에서 KMS 암호화 적용 확인
5. Keystone 토큰으로 kubectl 접근 가능 (`kubectl --token=<keystone_token> get nodes`)

### 20.6 범위 외

- 기존 `manifests.yaml.j2` (DaemonSet/Deployment) 파일 GC — 호출되지 않으나 보관, 차후 정리 PR
- apiserver 인증서 갱신 시 자동 재시작 트리거 — 운영 절차로 분리
- 외부 KMS 백엔드 (Vault 등) 추상화 — Barbican 한정 유지
- 통합 테스트 자동화 — 셀프호스티드 K3s 러너 필요, 본 작업은 단위 검증 중심

## 21. layerbuild CLI 검증 강화 (2026-05-10) — 9.1 Phase 1 안전망 도입

> **배경**: `scripts/layerbuild.py`(387라인)는 Builder VM에서 Union v2 레이어를 만드는 핵심 CLI. 9.1에서 코드는 [x] 완료지만 **단위 테스트 0건**, 9.1 인프라(Manila 3개 share + Builder VM)도 미설정 상태라 운영 검증 부재. 회귀를 잡을 안전망이 전혀 없었다.

### 21.1 `--dry-run` 글로벌 플래그 + `_run` helper

- [x] `scripts/layerbuild.py` — `_run(cmd, *, dry_run=False, ...)` 헬퍼로 모든 subprocess 호출 일원화. dry-run에서는 명령 트레이스(`$ mount --bind ...` 형태)만 출력, 실제 destructive 작업 미수행.
- [x] `_api_get` / `_api_post`도 dry-run 분기 추가 — stub 응답 반환.
- [x] `_compute_layer_hash`도 dry-run에서는 placeholder hash(`sha256:0...0`) 반환 (옵션 B — 흐름 트레이스가 본질, real hash는 단위 테스트로 검증).
- [x] dry-run 원칙: state file 미작성, mkdir 미수행 → **chainable 아님** (단일 명령 단위로만 동작). 사용자가 `init→exec→seal` 시퀀스를 미리 보려면 각 명령 독립 호출.
- [x] argparse에 `--dry-run` 글로벌 플래그 추가, 모든 cmd 함수가 `args.dry_run` 전달받음.

### 21.2 API 등록 실패 복구 — `.api_pending` 마커 + `cmd_resume_api`

- [x] `cmd_seal`이 API POST 예외 시 `dest_dir/.api_pending` 파일에 등록 payload(JSON) 저장. layer dir은 디스크에 이미 락 적용된 상태로 남아도 재시도 경로 확보.
- [x] 새 서브커맨드 `layerbuild resume-api <sha256:hash>` — `.api_pending` 읽고 POST 두 번 (등록 + 봉인) 재시도 → 성공 시 마커 삭제.
- [x] `_require_api_env()` 헬퍼로 환경변수 사전 검증 (cmd_init parent 지정 시, cmd_resume_api에서 호출).

### 21.3 단위 테스트 신규: `backend/tests/test_layerbuild.py` (21건)

- [x] **Pure 헬퍼 (5)**: state I/O 라운드트립, `_compute_layer_hash` 결정성/콘텐츠 변경 검출/빈 디렉토리/dry-run placeholder. **GNU tar(`--sort=name`) 미설치 환경(macOS BSD tar)에서는 hash 결정성 테스트 3건 자동 skip** — `_has_gnu_tar()` 가드.
- [x] **argparse (3)**: --version 필수 검증, 글로벌 --dry-run 파싱, resume-api 서브커맨드.
- [x] **cmd_init (5)**: parent 없을 때 bind mount + state 생성, parent 지정 시 `_api_get` 조상 체인 → lowerdir 조립 검증, state 충돌 시 exit 1, dry-run에서 mount/state 미생성, parent + API env 미설정 시 명확한 exit.
- [x] **cmd_seal (4)**: state 없으면 exit, API POST 두 번 순서 (`/api/union/layers` → `/api/union/layers/{id}/seal`), API 실패 시 `.api_pending` 마커 + content_hash 포함, dry-run 트레이스에 umount/chmod/chattr 포함.
- [x] **cmd_abort (2)**: state 없으면 조용히 종료, umount + work rmtree + state 클리어.
- [x] **cmd_resume_api (2)**: 마커 읽고 POST 두 번 → 마커 삭제, 마커 없으면 exit 1.
- [x] **결정성 보장 fixture**: `_normalize_dir(path)`가 모든 파일/디렉토리에 명시적 `chmod 0o644/0o755 + os.utime((0, 0))` 적용 → 환경 의존(umask, mtime) 제거.
- [x] **MagicMock 'parent' 속성 충돌 회피**: `argparse.Namespace` 사용 — MagicMock의 내부 `parent` 속성과 args.parent 충돌 방지.

### 21.4 검증

- [x] 백엔드 단위 테스트 1274건 그린 (1256 → 1274, +18 추가, 3건은 GNU tar 환경에서 추가 skip 해제 예정)
- [x] ruff check + format 통과
- [x] 수동 dry-run 검증: `python3 scripts/layerbuild.py --dry-run init test --version 1.0` → 명령 트레이스만 출력, 실제 mount/mkdir 미수행 확인

### 21.5 범위 외

- **Manila share 3개 실제 프로비저닝 + Builder VM 셋업** — 인프라 작업 (사용자 OpenStack 환경에서 수행). 본 plan 범위 외.
- **layerbuild fork/rebuild 새 서브커맨드** — Phase 3에 별도 항목.
- **GNU tar 의존을 Python `tarfile` 모듈로 분리** — cross-platform 가능하나 기존 GNU tar 동작과 정확히 일치한다는 보장이 어려움. 별도 PR.

## 22. Union 멀티 상속 실험 도입 (2026-05-10) — 9.3 마지막 [ ] 마감 (백엔드 한정)

> **배경**: union.md §4.2가 멀티 상속을 opt-in 실험 기능으로 정의 — 단일 상속 MVP 안정화 후 도입. 본 작업은 **백엔드 모델 + 서비스 + API**까지 도입하고, 단위/DB 통합 테스트로 다이아몬드/공통 base 검증 정책을 회귀 보호. layerbuild CLI 확장과 envmgr-use lowerdir 멀티 조립은 **별도 작업**.

### 22.1 설계 결정

- **mutually exclusive 모드**: single-parent는 `parent_id = X, parent_ids = NULL`, multi-parent는 `parent_id = NULL, parent_ids = [X, Y, ...]`. mirror 안 함 (advisor 검토 결과 — mirror하면 자식 검색 모호성 발생).
- **분기 조건**: `parent_ids is not None and len >= 2`. 1개짜리는 422 reject.
- **부모 순서는 정체성** (`union.md §4.2-2`): `[A, B]`와 `[B, A]`는 다른 레이어. overwrite 금지에서 JSON 비교.
- **공통 base 검증** (`union.md §4.2-4`): 모든 부모의 root ubuntu_base가 일치해야 함.
- **다이아몬드 dedup** (`union.md §4.2-3`): BFS + Kahn toposort + 선언 순서 결정성. 같은 조상이 여러 경로로 도달해도 한 번만 등장.

### 22.2 DB 스키마 + ORM

- [x] `backend/app/models/db.py` — `UnionLayer.parent_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)` 추가
- [x] `backend/app/database.py::create_tables` — `ALTER TABLE union_layers ADD COLUMN parent_ids JSON DEFAULT NULL` 마이그레이션 추가

### 22.3 Pydantic 모델

- [x] `backend/app/models/union.py::CreateLayerRequest`:
  - `parent_ids: list[str] | None = None` 추가
  - `field_validator`: 모두 sha256 형식 + dedup + 2개 이상
  - `model_validator`: parent_id와 parent_ids 동시 지정 시 422
- [x] `LayerInfo`: `parent_ids: list[str] | None = None` 응답 필드 추가

### 22.4 서비스 레이어

- [x] `backend/app/services/union_layers.py`:
  - `_is_multi_parent(layer) -> bool` 헬퍼 (`parent_ids and len >= 2`)
  - `_validate_common_base(session, parent_ids)` 신규 — 부모 root까지 거슬러 ubuntu_base 일치 검증
  - `create_layer` 분기: parent_ids 검증(봉인, 자기참조, 공통 base, overwrite 금지 — JSON list 비교)
  - `_get_ancestors_multi(session, leaf_id)` 신규 — Python BFS + Kahn toposort + 선언 순서 결정성 (base-first)
  - `get_ancestors`는 leaf의 모드(`_is_multi_parent`)로 single CTE / multi BFS 분기
  - `delete_layer` / `get_dependents`: single 자식(`parent_id == X`) + multi 자식(`JSON_CONTAINS(parent_ids, X)`) OR 검색. multi 자식은 모든 부모 차단.

### 22.5 API

- POST `/api/union/layers`: 기존 시그니처 유지 (CreateLayerRequest 확장만으로 자동 호환)
- GET `/api/union/layers/{id}/ancestors`: 내부 분기로 자동 처리

### 22.6 단위 테스트 — `TestMultiParent` 11건

- [x] create 성공/실패 6건: success, unsealed_rejected, base_mismatch_rejected, single_item_rejected (Pydantic), both_specified_rejected (Pydantic), overwrite_rejected
- [x] ancestors 2건: diamond_dedup (D 한 번만), multi_topo_order (선언 순서)
- [x] delete 1건: blocked_by_multi_parent_child (A/B 두 부모 모두 차단)
- [x] helper 2건: validate_common_base consistent / mismatch
- [x] `_make_layer` 헬퍼에 `parent_ids` 인자 추가 (MagicMock spec 자동 mock 회피)

### 22.7 DB 통합 테스트 — `test_union_layers_db.py` C3-21

- [x] **다이아몬드 토폴로지 실 SQL 검증**: D→{A, B} → C(parent_ids=[A, B]). C의 조상 체인에 D가 한 번만 등장 + base-first 순. multi 자식 차단 검증 (A/B 둘 다 409).
- MariaDB 11.4 (`@pytest.mark.db`) 환경에서 JSON_CONTAINS 실 동작 검증.

### 22.8 검증

- [x] 백엔드 단위 테스트 1285건 그린 (1274 → 1285, +11 신규)
- [x] union_layers 단위 96건 그린 (회귀 없음)
- [x] ruff check + format 통과
- DB 통합 1건은 셀프호스티드 MariaDB 잡 또는 사용자 환경에서 1회 검증

### 22.9 범위 외

- **layerbuild CLI `--parents A,B,C` 확장** — 별도 작업. 본 plan은 backend API만.
- **envmgr-use 멀티 lowerdir 조립** — 사용자 VM 측 변경. `get_ancestors` 응답을 reverse하여 사용하면 자동 호환.
- **충돌 경로 탐지 (silent shadowing 경고)** — union.md §4.2-1. 빌드 시점 부모 디렉토리 비교 필요. 별도 PR.
- **부모 ID 순서를 hash 입력에 포함** — layerbuild의 `_compute_layer_hash`에 부모 metadata 포함. CLI 변경 동반.
- **join table로 마이그레이션** — 멀티 상속 사용량 증가 후 정식 채택 시 별도 PR.

---

## 23. Admin Orphan Resource Detection API (2026-05-10) — 운영 가시성 신규

### 23.1 동기

- VM 삭제·빌드 정리 best-effort 경로(`instances.py`, `library_builder.py`)에서 단계적 실패 시 **분리된 FIP** 또는 **장기 미사용 volume**이 누적.
- 기존 admin/floating-ips, admin/all-volumes는 전체 목록만 노출 → 운영자가 수동으로 이상 항목을 식별해야 함.
- **본 작업**: 한 화면에서 orphan 후보를 검색 + 안전 일괄 정리하는 admin 전용 API 도입.

### 23.2 API

- [x] `GET /api/admin/orphans?min_age_days=14` → `{floating_ips: [...], volumes: [...]}` 반환
- [x] `POST /api/admin/orphans/cleanup` body `{kind: "floating_ip"|"volume", ids: [...]}` → `{deleted: [...], failed: [{id, error}]}`
- [x] 두 엔드포인트 모두 `require_admin` 의존, admin scope 토큰 + `all_projects=True`로 cross-project 가시성

### 23.3 검출 정책

- [x] **Floating IP**: `port_id IS NULL` → 즉시 orphan (분리된 즉시)
- [x] **Volume**: `status=available` + `attachments=[]` + `age_days >= min_age_days`(기본 14, 범위 [1, 365])
- [x] `min_age_days=0` 미허용 — 갓 detach된 정상 volume 보호

### 23.4 cleanup 안전 가드 (race-safe)

- [x] **Volume**: delete 직전 `cinder.get_volume` 재조회 → `attachments != []` 또는 `status != available`이면 `failed[]`에 추가, delete 호출 안 함.
- [x] **FIP**: 단순 delete + 예외 catch (분리된 FIP 재attach는 운영자 의도 행위로 race 위험 낮음).
- [x] 각 ID별 audit log 기록 (`rec(... action="orphan.cleanup", status="success"|"failed")`)

### 23.5 단위 테스트 — `test_admin_orphans.py` 12건

- [x] `find_orphan_floating_ips` — port_id NULL 필터 + age_days 계산 (2건)
- [x] `find_orphan_volumes` — min_age_days 필터 + attachments 제외 (2건)
- [x] `cleanup_floating_ips` — 정상 + 부분 실패 (2건)
- [x] `cleanup_volumes` — attachments race / status race / 정상 (3건)
- [x] 엔드포인트 — 비관리자 403 / 잘못된 kind 422 / volume cleanup audit log (3건)

### 23.6 검증

- [x] 백엔드 단위 1297건 그린 (1285 → 1297, +12 신규)
- [x] ruff check + format 통과
- 실 환경 검증 (사용자 1회): `GET /api/admin/orphans` → ID 1개 cleanup → 해당 ID 사라짐 / 비관리자 토큰 → 403

### 23.7 범위 외

- **Manila share orphan 검출** — project 삭제 후 잔존 share. 사용자 데이터 잠재 손실 위험으로 별도 PR. → §24에서 마감.
- **Security group orphan 검출** — afterglow 자동 생성 SG attach 0건. 운영자 정책 변경 가능성. 별도 PR. → §24에서 마감 (description marker 도입).
- **프론트엔드 admin/orphans 페이지** — 백엔드 API만 본 PR. UI 별도 PR.
- **Redis 캐싱** — 호출 빈도 분석 후 별도 PR.
- **Cron 자동 cleanup** — 명시적 작업 유지(안전 우선). 알림만 향후 검토.

---

## 24. Admin Orphan 검출 확장 — Manila share + Security group (2026-05-10)

### 24.1 동기

§23(FIP/Volume)에서 의도적으로 분리해 두었던 두 종류를 같은 엔드포인트에 통합. 둘 다 단일 SDK 응답으로 분별 불가:

- **Manila share**: project가 Keystone에서 사라진 share를 cleanup. project_id 매칭 + Keystone admin 조회 필요.
- **Security group**: afterglow가 자동 생성한 SG(`node_exporter`, `dcgm_exporter`, `union-egress-default`) 중 미부착건 cleanup. 일반명이라 사용자 SG와 충돌 위험 → **description marker 도입으로 분별책 확보**.

### 24.2 SG description marker 도입 (선결)

- [x] `app/services/neutron.py` 상단에 `AFTERGLOW_MANAGED_TAG = "[afterglow-managed]"` 모듈 상수 추가
- [x] 3개 ensure 함수의 description 끝에 ` {tag}` 접미어 부여 — `ensure_union_egress_sg`, `ensure_node_exporter_sg`, `ensure_dcgm_exporter_sg`
- [x] 신규 생성 SG부터 marker 부여. 기존 SG는 idempotent 경로가 description 갱신을 안 하므로 자동 제외(안전 우선). backfill은 별도 PR.

### 24.3 API 확장

- [x] `OrphanCleanupRequest.kind` Literal 확장: `"floating_ip" | "volume" | "manila_share" | "security_group"`
- [x] `OrphanScanResponse`에 `manila_shares`, `security_groups` 필드 추가
- [x] `OrphanShareInfo` (size_gb, project_id, status, snapshot_count 등), `OrphanSecurityGroupInfo` (description, project_id 등) 신규 모델
- [x] `cleanup_orphans` 엔드포인트에 `elif req.kind == "manila_share" / "security_group"` 분기 추가
- [x] 각 ID별 audit log (기존 `rec` 패턴 재사용)

### 24.4 Manila share 안전 가드

- [x] 검출: `manila.list_file_storages(conn, all_tenants=True)` × `keystone.list_all_project_ids()` 차집합. `is_public=True` 제외.
- [x] cleanup 직전 재검증:
  1. `get_file_storage` 재조회 (없으면 이미 삭제)
  2. `keystone.list_all_project_ids()` 재조회 후 project가 복구되었는지 확인 → 복구되면 fail
  3. `list_share_snapshots` 0건 확인 → snapshot 있으면 fail (사용자 데이터 보존 우선)
  4. `status in {available, error}` → 그 외 status는 fail
- [x] `keystone.list_all_project_ids()` 헬퍼 신규 추가 (`app/services/keystone.py`)

### 24.5 Security group 안전 가드

- [x] 검출: `conn.network.security_groups()` 중 `description.endswith(AFTERGLOW_MANAGED_TAG)` + `conn.network.ports()` bulk-fetch 후 attach 0건
- [x] cleanup 직전 재검증:
  1. 모든 port 한 번 fetch → `attached_sg_ids` 셋 빌드 (SDK list-query 가정 회피)
  2. SG 재조회 → marker 재확인 (없으면 fail — 사용자 SG 가능성)
  3. attached 셋 포함 여부 → 포함되면 fail (race)
  4. 통과 시 `neutron.delete_security_group`

### 24.6 정책 사유 (운영자 참고)

- **`is_public=True` Manila share 제외** — project 삭제와 무관하게 운영자/타 프로젝트가 의도적으로 공유한 자원이므로 cleanup 후보 아님.
- **SG description marker 미부여 = 사용자 SG로 간주** — afterglow가 만든 SG만 marker가 있으므로, marker 부재 SG는 자동으로 안전.
- **min_age_days 미적용 (Manila/SG)** — Manila는 project 부재, SG는 marker+attach=0이라는 binary 조건이므로 age 필터가 의미 흐림.

### 24.7 단위 테스트 — `test_admin_orphans.py` +10건

- [x] Manila: invalid project_id 추출 (`all_tenants=True` 호출 검증), is_public 제외 (2건)
- [x] Manila cleanup: project 복구 차단, snapshot 차단, 정상 (3건)
- [x] SG find: marker 요건 (None / "" / suffix 미일치 모두 제외) (1건), attach 1건 이상 제외 (1건)
- [x] SG cleanup: race attach 차단, marker 사라짐 차단, 정상 (3건)

### 24.8 프론트엔드

- [x] `/admin/orphans` 페이지에 두 섹션(Manila, SG) 추가 — 컬럼 / 체크박스 / select-all / 일괄 정리 버튼 패턴 그대로 차용
- [x] 정리 확인 모달에 종류별 안내문 (Manila: project 복구/snapshot 재검증, SG: port re-fetch + marker 재확인)
- [x] SG 섹션 상단에 marker 정책 인라인 안내

### 24.9 검증

- [x] 백엔드 단위 1297 → 1307 (+10), ruff/format 통과
- [x] 프론트엔드 빌드 통과
- 실 환경 검증 (사용자 1회): GET 4종 후보 노출 / 사용자 SG가 후보에 없음 / 1개 cleanup → race-safe 응답

### 24.10 범위 외

- **기존 SG description backfill** — 운영 환경의 기존 SG에 marker 일괄 부여하는 마이그레이션. 별도 PR.
- **Manila metadata 기반 검출** (`union_project_id` 메타 무효 사례) — 본 plan은 OpenStack `share.project_id` 매칭이 1차.
- **사용자가 description에 marker를 박는 행위** — 운영자 책임. UI 안내문에 명시.

---

## 25. 통합 모니터링 전(全) 리소스 가시성 + Drover 카운트 버그 수정 (2026-05-10)

### 25.1 동기

`/admin/monitoring` "클러스터 요약"이 일부 리소스만 집계하고 있었음:
- **Drover 클러스터 1대(`dms-cloud`, ACTIVE)인데 0으로 표시** — `_collect()`가 동기 함수인데 `k3s_db.list_all_clusters()`는 async라 `k3s_count: 0` 하드코딩(`admin.py:423-425` 옛 코드).
- DB 인스턴스 / Volume Snapshot/Backup / Share Snapshot / Image / Subnet / Security Group / Load Balancer / 사용자·프로젝트 수가 노출되지 않았음.

### 25.2 핵심 제약 — cross-project 보장

사용자 불만의 본질이 "admin scope 일부만 보이는 것"이라, 추가하는 모든 카운터는 **admin scope에서 cross-project 합산**을 보장.

- [x] Trove DB: `list_instances_admin_all_projects(conn)` (`/mgmt/instances`) — `count_instances`는 자기 프로젝트만이라 사용 안 함
- [x] Volume snapshot/backup: `conn.block_storage.snapshots/backups(all_projects=True)`
- [x] Share snapshot: `manila.list_share_snapshots(conn, all_tenants=True)` — `manila.py:710` 함수에 `all_tenants` 옵션 신규 추가
- [x] Octavia LB: `conn.load_balancer.load_balancers()` — admin scope에서 cross-project. `provisioning_status == "ACTIVE"`로 active 분리
- [x] Subnet/Security Group/Image: admin scope에서 SDK 기본 호출이 cross-project (admin.py 기존 패턴)
- [x] Identity: `_get_admin_ks_client().users.list()` / `.projects.list()` 길이

### 25.3 _collect async 변환 (Drover 버그 수정)

- [x] `get_monitoring_summary` 내부 `_collect`를 async로 변환. `cached_call`은 이미 `iscoroutinefunction` 분기로 async fn 처리(`cache.py:110-113`)
- [x] 동기 SDK 호출 15종을 `asyncio.to_thread + asyncio.gather`로 병렬 실행
- [x] k3s 클러스터는 `await k3s_cluster.list_all_clusters()` 직접 호출 — `k3s_count`/`k3s_active` 정상 노출

### 25.4 응답 스키마 확장 (호환 유지)

기존 4개 그룹 유지 + 누락 필드 추가 + 신규 그룹 2개:
- `storage`: `volume_snapshot_count`, `volume_backup_count`, `share_snapshot_count`, `image_count` 추가
- `network`: `subnet_count`, `security_group_count`, `load_balancer_count`, `load_balancer_active` 추가
- `containers`: `k3s_active` 추가 + `k3s_count` 정상 노출
- `data_services` (신규): `database_instance_count`
- `identity` (신규): `user_count`, `project_count`

### 25.5 드롭 항목 (의도적 제외)

- **Keypair 카운트** — Nova keypair는 per-user. admin도 자기 keypair만 보임 → cluster-wide 합산 불가능. 제외.
- **Swift container 카운트** — admin account 한정. cross-project 합산은 Swift reseller 권한 + 사용자 iteration 필요. 별도 PR.

### 25.6 프런트엔드 카드 재구성

- [x] `MonitoringSummary` interface에 신규 필드 (옵셔널 + `?? 0` 안전)
- [x] 스토리지 카드: 5줄 추가 (파일/볼륨 스냅샷·백업/파일 스냅샷/이미지)
- [x] 네트워크 카드: 3줄 추가 (Subnet / SG / LB)
- [x] 컨테이너 카드: Drover에 `(N active)` 배지
- [x] 신규 카드 2개: 데이터 서비스(Trove), Identity(사용자·프로젝트)

### 25.7 단위 테스트 — `test_admin_monitoring.py` 5건

- [x] k3s `[{status:"ACTIVE"}]` mock → `k3s_count == 1`, `k3s_active == 1` (Drover 버그 수정 회귀 방지)
- [x] k3s 빈 리스트 → 둘 다 0
- [x] 신규 그룹 `data_services` / `identity` 키 + 누락 필드 응답 포함 확인
- [x] 카운터 함수 일부 예외 시 다른 카운터 정상 (0 fallback)
- [x] async `_collect`가 `cached_call` `iscoroutinefunction` 분기에서 정상 동작

### 25.8 검증

- [x] 백엔드 단위 1307 → 1312 (+5), ruff/format 통과
- [x] 프런트엔드 빌드 통과
- 실 환경 검증 (사용자 1회): Drover 카드에 1 (1 active) 노출, 새 카드 2개 정상, 누락 리소스 표시

### 25.9 범위 외

- **각 리소스 상태 분포 차트 / 시계열** — 본 PR은 카운트만.
- **Keypair / Swift container** — admin scope 한계로 본 PR 제외 (위 25.5 참조).
- **인스턴스 status 외 세부 분포 (Trove/k3s/LB)** — total + active 1차만.
- **사이드바 재배치** — 기존 카드 유지.

---

## 26. DB 인스턴스 — 사용자 host 지원 / 호스트 정보 표시 / SHUTDOWN 라벨 (2026-05-11)

### 26.1 동기

- DB 사용자 생성이 500 에러 — `conn.database.create_user(instance_id, **user_body)` 가 Trove API 본문(`{"users":[{...}]}`)을 정확히 wrap 하지 못함.
- 사용자 생성 폼이 Trove user identity(`name@host`)의 host 필드를 노출하지 않음 — 동명 다른 host 유저 생성 불가.
- DB 인스턴스 IP 표시가 평탄 리스트라 어떤 네트워크 IP인지 불명확.
- 관리자 페이지에서 삭제 진행 중인 인스턴스가 raw `SHUTDOWN` 상태로만 표시되어 사용자 혼란.

### 26.2 백엔드

- [x] `services/trove.py::create_user` — raw REST(`conn.database.post(/instances/{id}/users)`) 로 교체. `host` 파라미터 추가 (기본 `%`), 페이로드는 `{"users":[{...}]}`.
- [x] `services/trove.py::delete_user` — raw REST(`conn.database.delete(/instances/{id}/users/{name@host})`) 로 교체. host-blind 삭제 방지 (동명 다른 host 유저 구분).
- [x] `services/trove.py::list_users` — 응답 dict 에 `host` 필드 포함 (`getattr(u, "host", "%")`).
- [x] `services/trove.py::_instance_to_dict` — `address_map: dict[str, list[str]]` 추가. Trove `i.addresses` dict → `{"private": ["192.168.0.10"]}` 매핑.
- [x] `models/database.py::CreateUserRequest` — `host: str = "%"` 필드 추가.
- [x] `api/database/instances.py::create_instance_user` — `req.host` 전달 + 실패 시 exception 로그.
- [x] `api/database/instances.py::delete_instance_user` — `host` query param 추가, `trove.delete_user` 에 전달.
- [x] `tests/test_db_users.py` — raw REST payload / host 기본값 / databases 형식 / delete URL host 인코딩 / list_users host / address_map 빌드/빈/우선순위 검증 (12건).

### 26.3 프런트엔드

- [x] `lib/config/statusColors.ts` — `StatusStyle.label?: string`, `SHUTDOWN: { tone: 'neutral', pulse: true, label: '삭제 중' }`.
- [x] `lib/components/ui/StatusChip.svelte` — `s.label ?? status` 로 라벨 우선 사용.
- [x] `lib/components/database/DbInstanceDetailPanel.svelte`:
  - `address_map` 우선, `ips` fallback 으로 "private: 192.168.0.163" 표시 (인스턴스 정보 / 연결 정보 두 영역).
  - 플레이버 ID → `cpu.4c_8g (4vCPU / 8192MB)` 매핑 (`/api/database-instances/flavors` 1회 fetch + 클라이언트 매핑).
  - 사용자 생성 폼: `host` 입력 + 인스턴스 DB 체크박스 선택 (databases 빈 경우 안내).
  - 사용자 목록: `name@host` 표시, 삭제 시 `host` 기준 식별.
  - 인스턴스 헤더 status 라벨에 `SHUTDOWN → "삭제 중"` 표시.

### 26.4 검증

- [x] `tests/test_db_users.py` 10건 + 기존 24건 통과 (총 34건)
- [x] `npm run lint:backend` 통과
- 실 환경 검증 필요 (사용자): 동명 다른 host 유저 동시 생성 / Horizon 형식 IP 표시 / SHUTDOWN 회색 펄스 + "삭제 중" 라벨

### 26.5 범위 외

- **Trove `mgmt/instances/{id}` 폴백** — `i.addresses` 가 비어있을 때 admin API 로 강제 조회. 현재는 `ips` fallback 으로 충분.
- **다른 프로젝트 인스턴스 IP 매핑** — Trove 가 사용자 네트워크에 NIC를 연결하지만 인스턴스 자체는 service tenant 소유. 사용자 권한 내 가능한 정보만 표시.
- **사용자 권한 세분화 (READ/WRITE/ADMIN)** — Trove `databases` 권한 부여만 지원.

---

## 27. DB 인스턴스 — `is_public` floating IP 자동 할당 (2026-05-11)

### 27.1 동기

`is_public=True` 로 생성해도 인스턴스에 public IP 가 잡히지 않음. 기존 동작은 `set_instance_access` 만 호출 — Trove 의 access 정책(allowed_cidrs)만 설정하고 floating IP 는 자동 할당하지 않음. 사용자는 "public 으로 표시 = 외부 접근 가능" 으로 기대 → floating IP 자동 할당 필요.

### 27.2 설계

- **`is_public` 의미 확장**: Trove access 정책 + afterglow 의 floating IP best-effort 자동 할당. `set_instance_access` 동작은 유지.
- **신규 인스턴스**: BackgroundTask 로 IP 폴링(5초 간격, 최대 10분) → port 매칭 → 라우터의 외부 네트워크 자동 탐색 → FIP 생성/할당.
- **기존 인스턴스**: DbInstanceDetailPanel 에 "+ 공개 IP 할당" 버튼 (FIP 미할당 시 노출). 사용자 conn 으로 동기 실행.
- **외부 네트워크 선택**: `find_external_network_for_subnets` 자동 탐색 (라우터 → external_gateway_info.network_id). 사용자 명시 선택은 미도입.
- **Port 탐색**: `device_id` 매칭은 service tenant 소유라 불안정 → IP fixed_ips 매칭으로 변경. Trove backend port 는 사용자 네트워크에 attach 되어 user conn 에서 조회 가능.

### 27.3 백엔드

- [x] `api/database/instances.py::_attach_fip_to_instance_sync` — IP→port→external network→FIP 동기 헬퍼. 멱등(이미 할당된 port 는 기존 FIP 반환).
- [x] `api/database/instances.py::_run_attach_fip_bg` — admin connection 으로 BUILD 폴링 + 자동 할당 BG task.
- [x] `api/database/instances.py::create_database_instance` — `BackgroundTasks` 파라미터 + `is_public` 시 BG 등록.
- [x] `api/database/instances.py::attach_floating_ip` — `POST /api/database-instances/{id}/floating-ip` 수동 할당 엔드포인트.
- [x] `api/database/instances.py::detach_floating_ip` — `DELETE /api/database-instances/{id}/floating-ip?delete=true` 해제(또는 삭제).
- [x] `tests/test_db_floating_ip.py` — port 매칭 / 멱등 / IP 미할당/port 미발견/외부망 미발견 에러 검증 (5건).

### 27.4 프런트엔드

- [x] `DbInstanceDetailPanel.svelte` — `FloatingIp` interface, `floatingIps` state, `instanceFips` derived (instance.ips ↔ fip.fixed_ip_address 매칭).
- [x] 연결 정보 섹션에 "공개 IP (Floating)" 행 추가:
  - 미할당 시: "+ 공개 IP 할당" 버튼 (instance.ip 대기 중이면 disabled)
  - 할당된 경우: 에메랄드 칩 + "해제" / "삭제" 버튼
- [x] `attachFip()` / `detachFip(deleteFip)` 함수, 에러 인라인 표시.
- [x] `loadAll()` 에 `/api/networks/floating-ips` 병렬 로드 추가.

### 27.5 검증

- [x] 백엔드 1333 → 1338 (+5), lint/format 통과
- [x] 프런트엔드 타입 체크 통과
- 실 환경 검증 필요 (사용자):
  - 신규 `is_public=true` 생성 → 몇 분 내 BG task 가 FIP 자동 할당
  - 기존 4개 인스턴스에 대해 패널에서 "+ 공개 IP 할당" 클릭 → FIP 즉시 할당
  - 라우터 미설정 환경에서는 "외부 네트워크 미연결" 에러 표시

### 27.6 범위 외

- **외부 네트워크 명시 선택** — 다중 외부망 환경에서 사용자가 직접 선택. 현재는 첫 매칭 라우터의 external network 자동 사용.
- **FIP quota pre-check** — quota 초과 시 Neutron 에서 raise. afterglow 가 사전 검증하지 않음.
- **DbCreatePanel 안내문** — "is_public 시 FIP 자동 할당" 인라인 안내. 별도 PR.

---

## 28. k3s 클러스터 생성 asyncio loop 충돌 + 라우트 매칭 순서 + DB 백업 글로벌 목록 (2026-05-11)

### 28.1 동기

- **k3s 클러스터 생성 시 "Future attached to a different loop" 에러**: `keystone.ensure_cluster_manager_user` 가 sync 함수인데 내부에서 `asyncio.run(_db_get())` 으로 SQLAlchemy async session 호출. caller(`clusters.py:374`)는 `await asyncio.to_thread(...)` 로 thread 에서 실행 → thread 의 새 loop 가 SQLAlchemy connection pool 의 원래 loop affinity 와 충돌.
- **`/api/instances/availability-zones` 404**: `instances.py:110` `@router.get("/{instance_id}")` 가 먼저 등록되어 `availability-zones` 를 instance_id 로 해석. FastAPI 는 등록 순서 매칭.
- **`/api/database-instances/backups` 404**: 글로벌 백업 목록 GET 엔드포인트 부재 (DELETE 만 존재). DbCreatePanel 의 백업 복원 폼이 호출.

### 28.2 백엔드 — asyncio loop 충돌 해결

`asyncio.run` 패턴을 제거하고 caller chain 을 async 로 통일.

- [x] `services/keystone.py::ensure_cluster_manager_user` — `async def` 변환. DB 호출은 `await get_manager_credentials(...)` / `await save_manager_credentials(...)` 직접 호출. sync openstacksdk 호출은 `asyncio.to_thread` 로 wrap.
- [x] `services/keystone.py::create_app_credential_for_cluster` — `async def` 변환. `await ensure_...` + `asyncio.to_thread(_create_app_cred_sync, ...)`.
- [x] `services/keystone.py::delete_app_credential` — `async def` 변환 (best-effort). `await ensure_...` + `asyncio.to_thread(_delete_app_cred_sync, ...)`.
- [x] `services/keystone.py::_connect_as_manager` — 헬퍼 추출 (관리 사용자로 openstack.connect, code 중복 제거).
- [x] `services/keystone.py::_ensure_cluster_manager_user_sync_with_admin_conn` / `_create_app_cred_sync` / `_delete_app_cred_sync` — sync 부분 추출 → `asyncio.to_thread` 호출 가능.
- [x] `api/k3s/clusters.py:374, 556, 802` — `await asyncio.to_thread(_keystone.X, ...)` → `await _keystone.X(...)`.

### 28.3 백엔드 — 라우트 충돌 + 글로벌 백업 목록

- [x] `api/compute/instances.py` — `@router.get("/availability-zones")` 를 `/{instance_id}` 위로 이동 (line 92 다음). 기존 line 1804 정의 제거.
- [x] `api/database/instances.py::list_all_backups` — `@router.get("/backups")` 신규. `trove.list_backups(conn)` 호출 (instance_id 없이 전체). project-scoped conn 이라 별도 owner check 불필요.

### 28.4 테스트 업데이트

- [x] `tests/test_keystone_appcred.py` — sync 호출(`uid, pw = ensure_cluster_manager_user(...)`) → `asyncio.run(...)` wrap (4건).
- [x] 기존 1335 → 1338 통과 유지 (회귀 없음).

### 28.5 검증

- [x] 백엔드 1338 테스트 통과, lint/format 통과
- 실 환경 검증 필요:
  - k3s 클러스터 생성 → "different loop" 에러 없이 BUILD 진행
  - `/api/instances/availability-zones` GET 200 응답 (가용 영역 목록)
  - `/api/database-instances/backups` GET 200 응답 (DB 복원 폼에 백업 목록 노출)

### 28.6 범위 외

- **다른 sync keystone 헬퍼의 async 변환** — 동일 호출 패턴이 없는 sync 함수는 그대로 유지 (advisor 권고대로 fix 범위 제한).
- **다른 라우터의 정적-경로 vs `/{id}` 충돌 일괄 검증** — 본 PR 은 보고된 한 건만 수정.

### 28.7 후속: `project_manager_credentials` 테이블 누락 DDL 추가

asyncio loop fix 후 SQL 이 실제 실행되자 다음 에러가 노출됨:
```
pymysql.err.ProgrammingError: (1146, "Table 'afterglow.project_manager_credentials' doesn't exist")
```

`k3s_db.py::get_manager_credentials` / `save_manager_credentials` 가 raw SQL 로 read/write 하는데 ORM 모델 / DDL 누락. (k3s_db.py 의 raw SQL 참조는 이 테이블 1개뿐.)

- [x] `app/database.py::create_tables` — `project_manager_credentials` DDL 추가:
  ```sql
  CREATE TABLE IF NOT EXISTS project_manager_credentials (
    project_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    username VARCHAR(255) NOT NULL,
    encrypted_password TEXT NOT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_project_manager_credentials_user_id (user_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  ```
- [x] 검증: `database_auto_create_tables=True` (기본값) → 백엔드 startup 시 `_deferred_create_tables` 가 자동 실행하여 누락 테이블 생성.
- 사용자 검증: 백엔드 컨테이너 재시작 1회 → k3s 클러스터 재시도 → 정상 진행.

---

## 29. 콘솔 로그 전체 페이지 + GPU cloud-init 회귀 테스트 (2026-05-11)

### 29.1 동기

- **콘솔 로그 일부만 표시** — `InstanceDetailPanel` 의 콘솔 로그 패널은 length 200/10000줄 까지만. Horizon 처럼 새 탭에서 전체 콘솔 출력을 보고 싶다는 요청.
- **GPU 인스턴스 cloud-init 미실행 의심** — `gpu.1080ti_8c_16g` flavor 인스턴스 생성 후 GPU 메트릭 부재. 백엔드 진단 결과 `flavor.is_gpu` → True → `gpu_available=True` → `cloudinit_base.yaml.j2` 의 GPU 분기(install_dcgm_exporter.sh + dcgm-exporter.service) 활성화되어야 정상. 회귀 테스트로 backend 단의 user-data 정상 생성을 보장하고, 실제 진단은 사용자가 새로운 전체 로그 페이지로 검증.

### 29.2 백엔드

- [x] `api/compute/instances.py:get_console_log` — `length` 상한 `le=10000` → `le=100000`. 100k 라인까지 fetch 가능.
- [x] `tests/test_cloudinit_gpu.py` 신규 — `generate_userdata(gpu_available=True)` 결과 base64 디코드 후 검증:
  - `install_dcgm_exporter.sh` write_files 포함
  - `ubuntu-drivers autoinstall` 명령 포함
  - runcmd 에 `dcgm-exporter.service` enable 항목 포함
  - dcgm-exporter systemd unit 파일 + ExecStart 0.0.0.0:9400
  - CUDA_HOME export 포함
  - gpu_available=False 시 모든 GPU 항목 부재 (회귀 방지)

### 29.3 프런트엔드

- [x] `routes/dashboard/compute/instances/[id]/console-log/+page.svelte` 신규 — 풀스크린 로그 뷰어:
  - 검정 배경, monospace, ANSI escape raw 표시
  - sticky 상단 바: 인스턴스 ID, 새로고침/닫기 버튼, 마지막 로드 시간
  - `length=100000` 1회 fetch (자동 갱신 없음 — 큰 payload polling 회피, 사용자가 수동 새로고침)
  - `<svelte:head>` title 인스턴스 prefix
- [x] `lib/components/InstanceDetailPanel.svelte` — 콘솔 로그 패널에 "새 창에서 보기 ↗" 링크 추가 (`target="_blank"`).

### 29.4 검증

- [x] 백엔드 1338 → 1343 테스트 통과 (+5), lint/format 통과
- [x] 프런트엔드 타입 체크 통과
- 사용자 검증 필요:
  - 인스턴스 상세 → 콘솔 로그 → "새 창에서 보기 ↗" 클릭 → 풀스크린 페이지 표시
  - GPU 인스턴스에서 NVIDIA 설치 라인(`[gpu-install] NVIDIA 드라이버 미발견`) 새 페이지에서 확인 가능

### 29.5 후속 fix: GPU only 인스턴스의 user-data 누락 (2026-05-11)

**Root cause 확정**: 사용자가 전체 콘솔 로그를 공유 → cloud-init 이 130초만에 정상 완료했지만 NVIDIA 설치 단계 0건. `Frontend VmCreatePanel.svelte:291` 가 `/api/instances/async` 호출 → `instances.py:564` 의 `if resolved_libs:` 분기 안에서만 `cloudinit.generate_userdata()` 호출 → libraries=[] + GPU flavor 인스턴스는 **user-data 없이 부팅** → cloud-init 의 default cloud config 만 실행되고 NVIDIA 드라이버 미설치.

(동기 `create_instance` 핸들러 line 282 는 이 버그가 없음 — 항상 generate_userdata 호출. 하지만 frontend 가 `/async` 만 사용해서 노출됨.)

- [x] `api/compute/instances.py::create_instance_async` — cloud-init 생성 분기를 `if resolved_libs:` → `if resolved_libs or gpu_available:` 로 변경. Upper volume / Manila step 은 기존대로 `if resolved_libs:` 유지 (GPU only 인스턴스에는 불필요).
- [x] `tests/test_cloudinit_gpu.py::test_async_handler_generates_userdata_for_gpu_only_instance` — 분기 진리표 회귀 테스트 (4 케이스: libraries × GPU 조합).
- [x] 검증 안전성: `overlay_setup.sh` (set -euo pipefail) 는 systemd unit `union-overlay.service` 안에서만 실행 → mount 실패 해도 cloud-init runcmd 의 `/opt/union/install_dcgm_exporter.sh` 는 독립적으로 실행됨.
- [x] Nova create — `upper_volume_id=None` 일 때 attach skip (line 696 `if upper_volume_id:`).

### 29.6 사용자 작업 — 기존 인스턴스 NVIDIA 드라이버 설치

코드 fix 는 **신규 인스턴스부터 적용**. 기존 `test-nvidia-driver` 등 이미 만든 GPU 인스턴스에는 user-data 가 비어있어 자동 설치 안 됨. 두 옵션:

1. **인스턴스 재생성** — 가장 깔끔. 백엔드 재배포 후 동일 spec 으로 새로 생성.
2. **SSH 후 수동 설치**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y ubuntu-drivers-common
   sudo ubuntu-drivers autoinstall
   sudo reboot
   ```
   재부팅 후 `nvidia-smi` 로 확인. dcgm-exporter 가 필요하면 `cloudinit_base.yaml.j2` 의 install_dcgm_exporter.sh 내용을 참조해 수동 실행.

### 29.7 범위 외

- `ubuntu-drivers autoinstall` 이 1080ti(Pascal) 에 잘못된 드라이버 선택 가능성 — 신규 인스턴스 검증 후 문제 시 별도 PR.

---

## 30. 라이브러리 빌더 안정화 — end-to-end 동작 확정 (2026-05-12)

### 30.1 동기

라이브러리 빌드 파이프라인(library_builder.py prebuilt share 트랙)을 실 환경에서 end-to-end 동작 가능 상태로 만든다.
진단된 이슈 3건:
1. 유저 VM cloud-init runcmd `mkdir -p /opt/layers/{lower,upper,work,merged}` — Ubuntu `/bin/sh`(dash)는 brace expansion 미지원 → literal 디렉토리 생성, union-overlay.service 실패.
2. 빌더 VM vdb 50GB 블록 디바이스 정체 (flavor ephemeral 의심, OpenStack CLI 검증 대기).
3. prebuilt share end-to-end (빌드 → probe VERIFY_OK → 메타데이터 갱신) 미검증.

### 30.2 백엔드

- [x] `backend/app/templates/cloudinit_base.yaml.j2:246` — runcmd mkdir brace expansion fix:
  `mkdir -p /opt/layers/{lower,upper,work,merged}` → 4개 개별 인자로 분리
  (dash `/bin/sh` 호환, bash brace expansion 의존 제거)
- [x] `backend/tests/test_cloudinit_dirs.py` (신규) — brace expansion 회귀 테스트 3건:
  - runcmd mkdir 라인에 `{`/`}` 없음
  - 4개 디렉토리(`lower`/`upper`/`work`/`merged`) 모두 포함
  - file_storages 있어도 동일

### 30.3 진단 대기 (사용자 OpenStack CLI 결과 수신 후 Phase C 분기 결정)

```bash
# vdb 정체 확정
openstack flavor show b9d8422a-ef0a-47e5-9e55-3cb01c7f0d68 -c disk -c ephemeral -c swap -c ram -c vcpus
# 빌더 VM 빌드 로그
openstack console log show union-builder-python311 | tail -200
# 유저 VM union-overlay 실패 원인
sudo cat /var/log/union-overlay.log && ls /opt/layers/
```

### 30.4 검증

- [x] `npm run test:backend` 1369 passed (0 failed), lint 통과
- 사용자 검증 필요:
  - 신규 VM 생성 → `ls /opt/layers/` 에 literal `{...}` 없음
  - `mount | grep overlay` 에서 `/opt/layers/merged` 확인
  - `python3.11 -c "import sys; print(sys.path)"` 에 `/opt/layers/merged/...` 포함

### 30.3 추가 버그 수정 (코드 분석)

- [x] `backend/app/services/library_builder.py`
  - `_monitor_build:length=200` → `length=2000`: 콘솔 로그 잘림으로 성공 빌드를 실패 오판하는 CRITICAL 버그
  - `_cleanup_builder_resources` 헬퍼 추출: ERROR/타임아웃 케이스 공통 정리 (share metadata + builder CephX rule revoke + VM 삭제). 기존엔 access rule이 정리 안 돼 유령 CephX user 잔류.
- [x] `backend/app/services/manila.py`
  - `_get_access_key`: 20회 재시도 후 빈 문자열 반환 → `RuntimeError` 발생. 빈 key가 cloud-init에 주입되면 CephFS 마운트가 반드시 실패하므로 호출부에서 인지 가능하게.
  - `_revoke_access_rule_raw` 헬퍼 추가: key 발급 타임아웃 시 `create_access_rule`이 고아 rule 자동 revoke 후 예외 재발생.

### 30.4 검증

- [x] `npm run test:backend` 1369 passed (0 failed)
- 사용자 검증 필요:
  - 신규 VM 생성 → `ls /opt/layers/` 에 literal `{...}` 없음
  - `mount | grep overlay` 에서 `/opt/layers/merged` 확인
  - `python3.11 -c "import sys; print(sys.path)"` 에 `/opt/layers/merged/...` 포함

### 30.5 범위 외

- 빌더 flavor 교체 (ephemeral=0) — Phase C-1: OpenStack CLI 결과 확인 후
- CephFS 마운트 실패 근본 원인 — Phase C-3: 유저 VM overlay 로그 분석 후

## 31. 기존 부팅 볼륨에서 VM 부팅 (2026-05-12)

### 31.1 동기

부팅 가능한(`bootable=true`) Cinder 볼륨을 루트 디스크로 재사용해 VM을 생성하는 기능 추가.
기존엔 항상 이미지→볼륨 변환을 거쳐야 했으나, 스냅샷/백업으로 만든 부팅 볼륨을 직접 지정하면
이미지 변환 시간 없이 즉시 인스턴스를 생성할 수 있다.

### 31.2 백엔드

- [x] `backend/app/models/storage.py` — `VolumeInfo`에 `bootable: bool = False`, `volume_image_metadata: dict | None = None` 필드 추가
- [x] `backend/app/services/cinder.py` — `_vol_to_info`: bootable str→bool 정규화, volume_image_metadata 추출
- [x] `backend/app/models/compute.py` — `CreateInstanceRequest`: `image_id` optional화, `boot_volume_id: str | None` 추가, `model_validator`로 상호배타 검증
- [x] `backend/app/api/compute/instances.py` — step 2 분기: `boot_volume_id` 지정 시 `create_volume_from_image` 건너뜀, `available`/`bootable` 검증, rollback 시 제공된 볼륨 보호
- [x] `backend/tests/test_instance_boot_from_volume.py` (신규) — 6개 테스트: create_img_not_called, delete_on_termination_forced_false, 동시지정 422, 미지정 422, in-use 400, non-bootable 400

### 31.3 프런트엔드

- [x] `frontend/src/lib/types/resources.ts` — `Volume` 인터페이스에 `bootable?: boolean`, `volume_image_metadata?: Record<string, string> | null` 추가
- [x] `frontend/src/lib/stores/wizard.ts` — `WizardState`에 `bootSource: 'image' | 'volume'`, `bootVolumeId`, `bootVolumeName` 추가
- [x] `frontend/src/routes/dashboard/volumes/+page.svelte` — 부트 badge `vol.bootable` 기반으로 교체 + OS 정보 표시, ActionMenu에 "이 볼륨으로 VM 부팅" 항목 추가
- [x] `frontend/src/lib/components/VmCreatePanel.svelte` — Step 1: 이미지/기존 볼륨 토글, Step 5: bootSource=volume 시 루트 디스크 섹션 숨김, Step 6: 부트 소스 조건부 표시, deploy(): `boot_volume_id` 전송

### 31.4 검증

- [x] `npm run test:backend` 통과
- 사용자 검증 필요:
  - bootable 볼륨에서 ActionMenu "이 볼륨으로 VM 부팅" → 위저드 Step 1이 '기존 부팅 볼륨' 탭으로 열리고 해당 볼륨 선택 상태
  - 위저드에서 VM 생성 완료 → `POST /api/instances/async` 바디에 `boot_volume_id` 포함, `image_id` 없음
  - non-bootable / in-use 볼륨: ActionMenu 항목 미노출

---

## 32. K3s 클러스터 SSE 비동기 삭제 (2026-05-13)

### 32.1 동기

- 동기 `DELETE /api/k3s/clusters/{id}` 가 LB/K8s 노드/VM 대기/SG 순차 수행으로 30초 이상 소요.
- 프런트 `client.ts:72` 의 `AbortSignal.timeout(30_000)` 으로 클러스터가 정상 삭제되어도 `TimeoutError: signal timed out` alert 발생.
- Admin 동기 삭제에 LB / K8s 노드 / App Credential cleanup 미포함 → orphan 리소스 위험.

### 32.2 백엔드

- [x] `backend/app/models/k3s.py::K3sProgressStep` — delete 단계 8개 추가
- [x] `backend/app/api/k3s/clusters.py` — `_SSE_HEADERS` 모듈 상수 추출 (생성/삭제 공유)
- [x] `backend/app/api/k3s/clusters.py` — 공유 async generator `_delete_cluster_progress` 추출
- [x] `backend/app/api/k3s/clusters.py` — `POST /api/k3s/clusters/{id}/delete-async` SSE 엔드포인트 신설
- [x] `backend/app/api/k3s/clusters.py` — 기존 `delete_k3s_cluster` 동기 핸들러를 generator 소진형으로 리팩토링 (204 유지)
- [x] `backend/app/api/identity/admin.py` — `POST /api/admin/k3s-clusters/{id}/delete-async` 신설 (user 와 동일 generator)
- [x] `backend/app/api/identity/admin.py` — `delete_admin_k3s_cluster` 동기 핸들러도 generator 소진형으로 리팩토링 + LB/K8s/AppCred 단계 통일

### 32.3 프런트엔드

- [x] `frontend/src/lib/api/k3sSseStream.ts` (신규) — `streamK3sProgress` async generator 유틸 (30초 제한 우회)
- [x] `frontend/src/lib/components/k3sSteps.ts` (신규) — `K3S_CREATE_STEPS`, `K3S_DELETE_STEPS` 상수
- [x] `frontend/src/routes/dashboard/drover/+page.svelte` — `deleteCluster()` SSE 화, 진행 모달 mode 전환 (create/delete)
- [x] `frontend/src/lib/components/K3sClusterDetailPanel.svelte` — `deleteCluster()` SSE 화, 패널 인라인 progress bar

### 32.4 검증

- [x] `backend/tests/test_k3s_clusters.py` — SSE 테스트 6건 추가 (client.stream + aiter_lines 첫 도입)
- [x] 기존 동기 삭제 테스트 8건 통과 (44개 전체 통과 확인)
- [x] `npm run lint:backend` 통과
- 사용자 브라우저 검증 필요:
  - 클러스터 삭제 클릭 → 단계별 진행 모달 표시 (delete_init → ... → completed)
  - 30초 이상 소요 클러스터도 alert 없이 완료
  - 상세 패널 삭제 → 패널 내 progress bar 표시 → 완료 후 목록 페이지 이동
  - Admin 경로에서도 동일 동작

### 32.5 향후

- 생성 SSE 호출 (`drover/+page.svelte:190-258` 인라인)을 `streamK3sProgress` 유틸로 교체 (별 PR)

## 33. VM 생성 위저드 디자인 시스템 반영 (2026-05-13)

### 33.1 동기

- Afterglow Design System 번들 (`vm-wizard-improved.html`) 에서 도출된 6단계 위저드 시각/구조 개선.
- 현 위저드는 step indicator 평탄, quota 변화가 음수 표기로 직관성 낮음, cloud-init 일반 textarea, review 단조로움.
- 색상 변경 없이 **구조/타이포/radius/레이아웃만** 반영 (primary = blue-500/600 유지).

### 33.2 신규 컴포넌트

- [x] `frontend/src/lib/components/wizard/WizardStepper.svelte` — progress fill bar (warm gradient) + done dot 클릭 이동
- [x] `frontend/src/lib/components/wizard/WizardHeader.svelte` — 큰 타이틀 + STEP n/6 subtitle + 새로 시작 / ✕
- [x] `frontend/src/lib/components/wizard/WizardFooter.svelte` — selection chips strip (이미지·플레이버·라이브러리) + 네비게이션

### 33.3 기존 컴포넌트 개선

- [x] `SelectImage.svelte` — 검색바 + OS chip count + hover lift + check pill
- [x] `SelectFlavor.svelte` — quota delta 미터 grid (현재 회색 + 이번 VM 추가 blue fill), GPU stock pill delta
- [x] `SelectLibraries.svelte` — 의존성 met (✓ green) / missing (! red) 칩 + 버전/req 배지 + 하단 summary strip
- [x] `SelectStrategy.svelte` — list-card 패턴 + 우측 size-slot (⚡ ~30초 / ⏱ ~3-5분)
- [x] `VmCreatePanel.svelte` (Settings) — 2열 grid + cloud-init 다크 코드 에디터 (bg-[#0f172a]) + toolbar placeholder + 라벨 톤 통일
- [x] `VmCreatePanel.svelte` (Review) — row grid + 플레이버 4분할 spec card (vCPU/RAM/Disk/GPU) + 각 row ✎ 수정 + deploy banner

### 33.4 검증

- [x] `npm run check` — 위저드 관련 파일 신규 에러 없음 (기존 pre-existing 에러는 다른 파일)
- [x] `npm run build` — production 빌드 통과 (4.40s)
- [ ] 브라우저 수동 검증 (인스턴스 페이지 + admin/인스턴스 페이지)
- [ ] light mode 전환 가독성 확인

### 33.6 VM 스케줄링/HA 분리 (완료)

- [x] `backend/app/models/compute.py` — `CreateInstanceRequest.scheduling` (Literal["standard","ha"], 기본 "standard") + `InstanceInfo.scheduling` 추가
- [x] `backend/app/services/nova.py` — `_server_to_info()` 에서 metadata scheduling 읽어 InstanceInfo 채움
- [x] `backend/app/api/compute/instances.py` (sync/async 두 분기) — meta 에 `scheduling`, HA 시 `HA_Enabled=True` 추가
- [x] `backend/app/api/identity/admin_instances.py` — 동일 meta 패턴 적용
- [x] `backend/tests/test_instance_scheduling.py` — 신규 8개 테스트 (model default, _server_to_info metadata 파싱)
- [x] `frontend/src/lib/stores/wizard.ts` — `scheduling: 'standard' | 'ha'` 필드 추가 (기본 'standard')
- [x] `frontend/src/lib/components/wizard/SelectStrategy.svelte` — 재작성: 섹션 A(스케줄링 항상) + 섹션 B(레이어 마운트 방식, 라이브러리 있을 때만)
- [x] `frontend/src/lib/components/VmCreatePanel.svelte` — step skip 로직 제거, selectScheduling 핸들러, canNext step4 조건, deploy body에 scheduling, footer summary 업데이트
- [x] 62개 테스트 통과, `npm run check` 신규 에러 없음

### 33.5 향후 (별 PR)

- cloud-init YAML 실시간 검증 (js-yaml 도입) + 예제 프리셋 적용
- review deploy banner cost 추정 ($/hour → backend cost API 필요)
- OS 별 logo 컬러 매핑 (메모리 규칙 재확인 후)
- HA evacuate 실제 동작: cluster 에 Masakari 설치 + segment/host 등록 필요 (운영 문서 별도)

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

## 35. JWT access+refresh 토큰 도입 — Keystone 토큰 백엔드 격리 (2026-05-18)

### 35.1 동기

- Keystone 1시간 토큰을 localStorage에 평문 저장 → 보안 취약 + 자주 재로그인 필요
- Afterglow 자체 JWT 발급(access 15분 + refresh 7일): frontend는 JWT만 보유, Keystone 토큰은 backend Redis에 격리

### 35.2 신규 파일

- [x] `backend/app/services/jwt_service.py` — HS256 access/refresh 서명·검증 (`sign_access`, `verify_access`, `sign_refresh`, `verify_refresh`)
- [x] `backend/app/services/session_store.py` — `afterglow:refresh:{jti}` Redis 키로 Keystone 토큰 매핑 (TTL=refresh 만료까지)
- [x] `backend/tests/test_auth_jwt.py` — 14개 테스트: JWT 서명·검증, 세션 저장소, 로그인 응답, Bearer 인증, 레거시 X-Auth-Token, 만료 JWT 401, 토큰 회전(replay 방지), 로그아웃 후 refresh 401

### 35.3 백엔드 수정

- [x] `backend/app/api/identity/auth.py` — `/login`, `/gitlab/callback` 응답에 `token`(access JWT) + `refresh_token` 쌍 발급, `/refresh` 엔드포인트(토큰 회전), `/switch-project` 엔드포인트 추가
- [x] `backend/app/api/deps.py` — `Authorization: Bearer` 우선 처리 (`_resolve_jwt_token_info`), 레거시 `X-Auth-Token` fallback 유지 (dual-path)
- [x] `backend/app/models/auth.py` — `TokenResponse`에 `refresh_token: str | None` 추가
- [x] `backend/app/config.py` + `config.toml.example` + `generate_k8s.py` — `jwt_access_ttl=900`, `jwt_refresh_ttl=604800` 동기화
- [x] `backend/pyproject.toml` — `pyjwt>=2.9.0` 의존성 추가

### 35.4 프론트엔드 수정

- [x] `frontend/src/lib/stores/auth.ts` — `refreshToken`, `accessExpiresAt` 필드 추가, `getAccessSecondsRemaining()` 헬퍼
- [x] `frontend/src/lib/api/client.ts` — `Authorization: Bearer` 헤더 전환, 401 시 `tryRefresh()` + 1회 재시도, `_refreshPromise` coalescing으로 동시 refresh 직렬화
- [x] `frontend/src/routes/+layout.svelte` — session-info 폴링 제거, JWT exp 기반 60초 타이머 auto-refresh (만료 2분 전)
- [x] `frontend/src/routes/+page.svelte`, `auth/gitlab/callback/+page.svelte` — `accessExpiresAt` 저장, `refreshToken` 저장
- [x] 직접 fetch 헤더 Bearer 전환: `k3sSseStream.ts`, `vmCreateStore.svelte.ts`, `k3sClusterDetail.svelte.ts`, `objectBrowser.svelte.ts`, `admin/notion/+page.svelte`, `dashboard/drover/+page.svelte`

### 35.5 검증

- [x] 149개 백엔드 테스트 통과 (14개 신규 JWT 테스트 포함)
- [x] `npm run check` — PR 2 관련 신규 에러 없음
- [ ] 실 환경: 로그인 → 16분 후 access 자동 갱신 → API 정상 동작, 로그아웃 후 refresh 재사용 차단


---

## 36. JWT stale 제거 + admin role 변동 즉시 반영 + audit (2026-05-18)

### 36.1 동기

PR 35(JWT 도입) 이후 access JWT(TTL 15분) payload에 `is_system_admin`/`roles`가 박혀 **admin role 박탈 후 15분간 admin으로 인식**되는 stale 윈도우 발생. X-Auth-Token 경로의 60s 캐시보다 후퇴한 보안 수준.

### 36.2 변경 파일

- [x] `backend/app/services/jwt_service.py` — `sign_access()`에서 `roles`/`is_system_admin` 파라미터 및 payload 클레임 제거. JWT는 신원 정보(sub, username, project_id, project_name, jti, rjti)만 보유.
- [x] `backend/app/api/identity/auth.py` — `_build_token_response()`의 `sign_access()` 호출에서 해당 인자 제거. `TokenResponse` 응답에는 초기 렌더링용으로 계속 포함.
- [x] `backend/app/api/deps.py` — `_resolve_jwt_token_info()` 정상 경로(프로젝트 전환 없음)도 `_cached_validate()` 호출로 통합. JWT payload의 stale 권한 사용 제거. stale window: 15분 → 60초(캐시 TTL).
- [x] `backend/app/services/session_store.py` — 보조 인덱스 `afterglow:user-sessions:{user_id}` SET 도입. `store_session`에 SADD, `delete_session`에 SREM 연동. `revoke_user_sessions(user_id)` 신규: 사용자 전체 세션 즉시 삭제.
- [x] `backend/app/api/identity/admin_identity.py` — `assign_role`/`revoke_role`에 `Depends(get_token_info)` 추가. `_resolve_admin_ids()`로 admin_role_id 비교 후 분기: admin role 변동 → `revoke_user_sessions` + audit; 일반 role 변동 → audit만.
- [x] `frontend/src/lib/api/client.ts` — `/api/admin/` 경로 403 응답 시 `handleAdminForbidden()`: `isSystemAdmin=false` 강등 + `/dashboard` 이동. one-shot 가드로 무한 루프 방지.
- [x] `frontend/src/routes/admin/+layout.svelte` — `onMount` 시 `/me` 강제 호출하여 stale 캐시 우회 + 즉시 권한 동기화.

### 36.3 테스트

- [x] `backend/tests/test_auth_jwt.py` 확장 (51개 통과):
  - `test_access_payload_no_auth_claims`: JWT payload에 `roles`/`is_system_admin` 없음 검증
  - `test_revoke_user_sessions`: 사용자 전체 세션 삭제, 다른 유저 세션 불변
  - `test_revoke_user_sessions_empty`: 세션 없는 유저 → 0 반환
  - `test_bearer_jwt_uses_cached_validate_not_payload`: Bearer JWT 경로가 JWT payload 대신 `_cached_validate`로 권한 결정함을 검증
- [x] `backend/tests/test_admin_identity.py` 확장 (51개 통과):
  - `test_assign_admin_role_revokes_sessions`: admin role 할당 → `revoke_user_sessions` 호출 + `admin_role_grant` audit
  - `test_assign_non_admin_role_no_revoke`: 일반 role 할당 → `revoke_user_sessions` 미호출 + `role_grant` audit
  - `test_revoke_admin_role_revokes_sessions`: admin role 회수 → `revoke_user_sessions` 호출 + `admin_role_revoke` audit
  - `test_revoke_non_admin_role_no_revoke`: 일반 role 회수 → `revoke_user_sessions` 미호출 + `role_revoke` audit

### 36.4 검증

- [x] 51개 백엔드 테스트 통과
- [x] `ruff check` — 수정 파일 lint 통과
- [ ] 실 환경: admin role 박탈 후 즉시 강제 로그아웃 확인, /admin 접근 시 403 → /dashboard 이동 확인

## 37. Keystone System Scope(`system:all`) 도입 — 자기복제 권한 상승 차단 (2026-05-18)

### 37.1 동기

기존 admin 판별 정책("admin project + admin role")의 구조적 약점: 현 admin이
`/api/admin/roles/assign`으로 다른 사용자에게 `admin role on admin project`를 부여하면,
그 사용자도 자동으로 system admin이 된다(`require_admin` 만으로 막을 수 없음). 이를
Keystone system-scoped role (`scope.system=all`)로 대체하여 project-scope `assign_role`
호출로는 system admin이 만들어지지 않도록 차단. 호환 모드(`admin_legacy_project_policy=true`)로
한 릴리스 동안 기존 admin을 OR 인정하여 무중단 마이그레이션 지원.

### 37.2 변경 파일

- [x] `backend/app/config.py` — `_load_toml()` `[security]` 섹션 매핑 + `Settings.admin_legacy_project_policy: bool = True`
- [x] `generate_k8s.py` — `_render_toml_for_k8s()` 에 `[security]` 블록 추가 (configmap 인라인)
- [x] `backend/app/services/keystone.py` — `_is_system_admin` dual-mode 재작성:
  - `_has_system_admin_role(user_id)`: `role_assignments.list(system="all")` 검사
  - `_has_admin_project_role(user_id)`: 기존 project-scope 검사 (호환 모드용)
  - `_is_system_admin`: `_has_system_admin_role OR (admin_legacy_project_policy AND _has_admin_project_role)`
  - `invalidate_admin_caches()`: 캐시 리셋 헬퍼
- [x] `backend/app/api/identity/admin_identity.py` — System Roles 섹션 신규 엔드포인트 3개:
  - `GET /api/admin/identity/system-roles` — system:all admin 보유자 목록
  - `POST /api/admin/identity/system-roles/grant` — system role 부여 + 세션 즉시 무효화 + audit
  - `POST /api/admin/identity/system-roles/revoke` — system role 회수 + 세션 즉시 무효화 + audit

### 37.3 테스트

- [x] `backend/tests/test_keystone_system_scope.py` (신규, 4개):
  - `test_system_role_grants_admin_regardless_of_compat`: system role 보유 → 호환 모드 무관 True
  - `test_admin_project_role_with_compat_on`: project role + 호환 ON → True
  - `test_admin_project_role_with_compat_off`: project role + 호환 OFF → False
  - `test_no_role_returns_false`: 권한 없음 → False
- [x] `backend/tests/test_admin_identity.py` 확장 (3개):
  - `test_list_system_roles_requires_admin`: non_admin → 403
  - `test_grant_system_role_revokes_sessions`: grant → `revoke_user_sessions` + `admin_system_role_grant` audit
  - `test_revoke_system_role_revokes_sessions`: revoke → `revoke_user_sessions` + `admin_system_role_revoke` audit

### 37.4 마이그레이션 절차

1. **PR B 배포** (`admin_legacy_project_policy=true`, 호환 모드 ON) — 기존 admin 사용자 즉시 영향 없음.
2. 운영 admin 1명에게 system role 수동 부여:
   ```bash
   openstack role add --system all --user <user-id> admin
   ```
   Afterglow `/admin` 정상 동작 확인.
3. 기존 admin project 멤버 전원에게 system role 부여 — `POST /api/admin/identity/system-roles/grant` 일괄 호출.
4. **다음 릴리스**: `config.toml`에서 `[security] admin_legacy_project_policy = false` 전환.
5. **다다음 릴리스**: 호환 분기 코드 + `admin_legacy_project_policy` 설정 키 + `_has_admin_project_role` 헬퍼 제거.

**policy.yaml 권장 변경** (운영자 별도 적용):
```yaml
"identity:list_users": "role:admin and system_scope:all"
"identity:create_role_assignment_on_system": "role:admin and system_scope:all"
```

### 37.5 검증

- [x] 58개 백엔드 테스트 통과 (`test_keystone_system_scope.py` + `test_admin_identity.py` + `test_auth_jwt.py`)
- [x] `ruff check` + `ruff format` — 수정 파일 lint/format 통과
- [ ] 실 환경: system role 부여(CLI) → admin 라우트 정상, admin project 멤버십 제거 후에도 admin 유지
- [ ] 실 환경: system role 박탈 → 즉시 강제 로그아웃 + 다음 API 401
- [ ] 실 환경: 호환 모드 OFF에서 project-scope admin role 부여 → `/admin` 403 (자기복제 차단 확인)

---

## § 38 — System Admin 계정 관리 (CLI + 관리자 페이지)

**동기**: PR B(`e05d8c9`)로 system:all scope 판별과 grant/revoke 엔드포인트가 생겼지만, 운영자가 활용하려면 ① 첫 admin 부트스트랩 수단, ② 일상 관리 UI, ③ 마지막 admin lockout 방지가 필요하다.

### 38.1 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/app/api/identity/admin_identity.py` | `list_system_roles` 응답 enrich (`name/email/enabled`); `revoke_system_role` lockout 가드 (count≤1 → 422) |
| `backend/tests/test_admin_identity.py` | 3개 테스트 추가 (enrich 검증, 마지막 admin 422, 2명 시 200) |
| `scripts/manage_system_admins.py` (신규) | argparse CLI — `list/grant/revoke`, `--os-system-scope` 옵션 |
| `frontend/src/routes/admin/system-admins/+page.svelte` (신규) | 시스템 관리자 관리 페이지 |
| `frontend/src/lib/components/admin/system-admins/SystemAdminTable.svelte` (신규) | 목록 테이블 + 회수 버튼 (마지막 1명 disabled, self-revoke confirm) |
| `frontend/src/lib/components/admin/system-admins/SystemAdminGrantModal.svelte` (신규) | 사용자 검색 모달 → grant 호출 |
| `frontend/src/lib/components/AdminSidebar.svelte` | Identity 섹션에 '시스템 관리자' 메뉴 추가 |

### 38.2 CLI 사용법

```bash
# 환경 설정
export OS_AUTH_URL=https://keystone.example.com/v3
export OS_USERNAME=admin OS_PASSWORD=...
export OS_PROJECT_NAME=admin OS_USER_DOMAIN_NAME=Default

# 현재 system admin 목록
python3 scripts/manage_system_admins.py list

# 부여 (user_id 또는 name)
python3 scripts/manage_system_admins.py grant alice@example.com

# 회수 (lockout 가드 없음 — 부트스트랩/복구 수단)
python3 scripts/manage_system_admins.py revoke alice@example.com

# Keystone secure-RBAC 환경 첫 grant 부트스트랩
python3 scripts/manage_system_admins.py --os-system-scope grant <user-id>
```

### 38.3 검증

- [x] 43개 백엔드 테스트 통과 (`test_admin_identity.py` + `test_keystone_system_scope.py`)
- [x] `ruff format` — 수정 파일 포맷 통과
- [x] frontend 신규 파일 — svelte-check 에러 없음
- [ ] 실 환경: CLI `list` → 빈 목록 정상
- [ ] 실 환경: CLI `grant` → `GET /api/admin/identity/system-roles` 응답에 name/email 포함 확인
- [ ] 실 환경: UI `/admin/system-admins` — 1명 표시 시 회수 버튼 disabled
- [ ] 실 환경: UI grant 후 2명 → 첫 admin self-revoke → 즉시 로그아웃
- [ ] 실 환경: 1명 남은 상태에서 `curl POST .../revoke` → 422

---

## § 39 — 호환 모드 마이그레이션 완성 (가시화 + 일괄 promote + 안전망)

**동기**: PR B 도입 후 `admin_legacy_project_policy=true` 호환 모드에서 strict 모드(`=false`)로 전환하기 위해 운영자에게 필요한 도구가 부재했다. admin project 멤버 일괄 promote 자동화, 현재 모드 가시화, lockout 안전망을 추가해 마이그레이션 절차 Step 3·4를 실행 가능하게 했다.

### 39.1 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/app/api/identity/admin_identity.py` | `GET /identity/security-policy` (모드+카운트 반환), `POST /identity/system-roles/migrate-from-project` (일괄 grant) 신규 엔드포인트 |
| `backend/app/main.py` startup | compat OFF + system admin 0명이면 `_logger.error()` lockout 경고 |
| `backend/tests/test_admin_identity.py` | 4개 테스트 추가 (security-policy 403/정상, migrate 403/정상) |
| `scripts/manage_system_admins.py` | `migrate-from-project` 서브커맨드 추가 |
| `frontend/src/routes/admin/system-admins/+page.svelte` | security-policy 병렬 fetch + SecurityPolicyBanner + MigrateModal 통합 |
| `frontend/src/lib/components/admin/system-admins/SecurityPolicyBanner.svelte` (신규) | 3-상태 배너 (compat ON/OFF+count>0/OFF+count=0) |
| `frontend/src/lib/components/admin/system-admins/MigrateModal.svelte` (신규) | 일괄 마이그레이션 확인 다이얼로그 + 결과 표시 |

### 39.2 CLI 사용법

```bash
# 호환 모드 → strict 전환 직전 일괄 마이그레이션
python3 scripts/manage_system_admins.py migrate-from-project

# 출력 예시:
# OK: alice (a1b2...) granted (system admin)
# SKIP: bob (b2c3...) already system admin
# 완료: 1명 grant, 1명 skip, 0건 오류
```

### 39.3 검증

- [x] 47개 백엔드 테스트 통과 (`test_admin_identity.py` + `test_keystone_system_scope.py`)
- [x] `ruff check` + `ruff format` — 수정 파일 lint/format 통과
- [x] frontend 신규 파일 — svelte-check ERROR 없음 (a11y WARNING은 기존 패턴과 동일)
- [ ] 실 환경: compat ON 상태에서 UI 노란 배너 + "일괄 마이그레이션" 버튼 확인
- [ ] 실 환경: 마이그레이션 실행 → migrated/skipped 카운트 정확히 반환
- [ ] 실 환경: `admin_legacy_project_policy=false` 후 재시작 → 초록 배너
- [ ] 실 환경: compat OFF + system admin 0명 → startup ERROR 로그 + 빨간 배너

---

## § 40 — Drover Cluster Template CRUD (Magnum ClusterTemplate 도입)

**동기**: 사용자가 매번 k3s_version, agent_count, flavor, plugins를 직접 고르는 불편을 해소하고, 운영자가 표준 프리셋("GPU dev 3대 + Cinder CSI")을 정의해 사용자가 선택+override할 수 있는 Magnum ClusterTemplate 추상화 도입.

### 40.1 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/app/models/db.py` | `K3sClusterTemplate` ORM 신규, `K3sCluster`에 `template_id`/`template_snapshot` 컬럼 추가 |
| `backend/app/models/k3s.py` | `K3sClusterTemplateInfo`, `CreateK3sClusterTemplateRequest`, `UpdateK3sClusterTemplateRequest` Pydantic 모델 신규, `CreateK3sClusterRequest.template_id` 추가 |
| `backend/app/services/k3s_template.py` (신규) | CRUD 서비스 (soft-delete, 권한 분기: admin=All / user=public+own) |
| `backend/app/api/k3s/templates.py` (신규) | GET 목록/단건, admin POST/PATCH/DELETE 5개 엔드포인트 |
| `backend/app/api/k3s/__init__.py` | `k3s_templates_router` export |
| `backend/app/main.py` | `k3s_templates_router` 등록 (`service_k3s_enabled` 가드 하위) |
| `backend/app/api/k3s/clusters.py` | `create_k3s_cluster_async`에 `_apply_template()` 머지 (요청 본문 값 우선) |
| `backend/app/services/k3s_db.py` | `_cluster_to_dict` / `create_cluster_record`에 template 필드 추가 |
| `backend/app/api/identity/admin.py` | `GET /admin/k3s-cluster-templates` 미러 엔드포인트 |
| `backend/migrations/009_k3s_cluster_templates.sql` (신규) | `k3s_cluster_templates` 테이블 DDL + `k3s_clusters` ALTER |
| `backend/tests/test_k3s_cluster_templates.py` (신규) | 15개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `K3sClusterTemplate` 인터페이스 추가 |
| `frontend/src/lib/components/admin/drover/K3sClusterTemplateModal.svelte` (신규) | 생성/편집 모달 |
| `frontend/src/lib/components/admin/drover/K3sClusterTemplateCard.svelte` (신규) | 카드 컴포넌트 |
| `frontend/src/routes/admin/drover/templates/+page.svelte` (신규) | admin 전용 템플릿 관리 페이지 |
| `frontend/src/lib/components/dashboard/drover/K3sCreateClusterModal.svelte` | 템플릿 드롭다운 추가 + `applyTemplate()` |
| `frontend/src/routes/dashboard/drover/+page.svelte` | `createCluster`에 `template_id` 전달 |
| `frontend/src/lib/components/AdminSidebar.svelte` | "클러스터 템플릿" 메뉴 항목 추가 |

### 40.2 검증

- [x] 백엔드 15개 테스트 통과 (`test_k3s_cluster_templates.py`)
- [x] 기존 87개 테스트 회귀 없음
- [x] `ruff check` + `ruff format` — 수정 파일 통과
- [x] frontend svelte-check ERROR 없음 (a11y WARNING은 기존 패턴과 동일)
- [ ] 실 환경: admin 페이지에서 템플릿 생성 → 사용자 생성 모달 드롭다운 확인
- [ ] 실 환경: 템플릿 선택 후 agent_count/flavor override 동작 확인
- [ ] 실 환경: `public_visible=false` 템플릿이 타 사용자 드롭다운에 미노출 확인
- [ ] 실 환경: 템플릿 PATCH/DELETE 후 기존 클러스터 `template_snapshot` 보존 확인

---

## § 41 — PR 2A: Nodegroup 추상화 레이어 (2026-05-18)

### 41.1 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/migrations/010_k3s_nodegroups.sql` (신규) | `k3s_nodegroups` + `k3s_nodegroup_vms` DDL, 기존 클러스터 SQL 백필 |
| `backend/app/models/db.py` | `K3sNodegroup`, `K3sNodegroupVM` ORM 추가, `K3sCluster.nodegroups` 관계 |
| `backend/app/models/k3s.py` | `K3sNodegroupInfo`, `CreateK3sNodegroupRequest`, `UpdateK3sNodegroupRequest` 추가 |
| `backend/app/services/k3s_nodegroup.py` (신규) | CRUD 서비스 (list/get/create/update/delete + VM 추적 헬퍼) |
| `backend/app/api/k3s/nodegroups.py` (신규) | GET list, GET 단건, POST, PATCH, DELETE 라우터 |
| `backend/app/api/k3s/__init__.py` | `k3s_nodegroups_router` export 추가 |
| `backend/app/main.py` | nodegroups 라우터 `service_k3s_enabled` 가드 하위 등록 |
| `backend/tests/test_k3s_nodegroups.py` (신규) | 16개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `K3sNodegroup`, `K3sNodegroupVM` 인터페이스 추가 |
| `frontend/src/lib/components/dashboard/drover/K3sNodegroupCard.svelte` (신규) | 노드그룹 카드 컴포넌트 |
| `frontend/src/lib/components/dashboard/drover/K3sNodegroupCreateModal.svelte` (신규) | 노드그룹 생성 모달 |
| `frontend/src/lib/components/k3s/K3sNodegroupsSection.svelte` (신규) | 클러스터 상세 내 노드그룹 목록 + 생성/삭제 |
| `frontend/src/lib/components/K3sClusterDetailPanel.svelte` | `K3sNodegroupsSection` 임포트 및 배치 추가 |

### 41.2 검증

- [x] 백엔드 16개 테스트 통과 (`test_k3s_nodegroups.py`)
- [x] svelte-check — 신규 파일 ERROR 없음
- [ ] 실 환경: 기존 클러스터에 백필 SQL 실행 후 `GET /api/k3s/clusters/{id}/nodegroups` 응답 확인
- [ ] 실 환경: 노드그룹 생성 → 수정(node_count) → 삭제 흐름 확인
- [ ] 실 환경: default-server/default-agent 삭제 시 422 응답 확인
- [ ] 클러스터 상세 패널에 노드그룹 섹션 표시 확인

---

## § 42 — PR 2B: k3s 마스터 HA (embedded etcd, LB-first) (2026-05-18)

### 42.1 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/migrations/011_k3s_master_ha.sql` (신규) | `k3s_clusters.master_count INT NOT NULL DEFAULT 1` ALTER |
| `backend/app/models/db.py` | `K3sCluster.master_count` 컬럼 추가 |
| `backend/app/models/k3s.py` | `K3sProgressStep` HA 단계 추가, `CreateK3sClusterRequest.master_count` (1\|3 validator), `K3sClusterInfo.master_count` |
| `backend/app/services/k3s_cluster.py` | `create_ha_callback_token`, `consume_ha_callback_token`, `get_ha_join_count`, `incr_ha_join_count` 추가 |
| `backend/app/services/k3s_db.py` | `_cluster_to_dict`, `create_cluster_record`, `_column_map`에 `master_count` 추가, HA 토큰/카운터 래퍼 추가 |
| `backend/app/services/k3s_cloudinit.py` | `generate_server_userdata` + `_build_server_ignition`에 `cluster_init`, `join_url`, `ha_node_token` 파라미터 추가 |
| `backend/app/templates/k3s_server.yaml.j2` | `cluster_init`/`join_url` HA 분기 추가 |
| `backend/app/services/k3s_provisioner.py` (신규) | `provision_agents` (callback.py에서 이전) + `bootstrap_ha_servers` |
| `backend/app/api/k3s/clusters.py` | Step 1-B HA LB+FIP 생성, `cluster_init` 전달, HA 필드 저장, `_rollback` lb_id/fip_id, `_cluster_to_info` master_count |
| `backend/app/api/k3s/callback.py` | HA/일반 토큰 이중 시도, server_index 분기, `_handle_ha_joiner`, provision_agents → k3s_provisioner 이전 |
| `backend/app/config.py` | `k3s_api_lb_floating_network_id` 추가 (Settings + _load_toml) |
| `backend/tests/test_k3s_master_ha.py` (신규) | 11개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `K3sCluster.master_count?: number` 추가 |
| `frontend/src/lib/components/dashboard/drover/K3sCreateClusterModal.svelte` | `master_count` 폼 필드, 1/3 토글 UI 추가 |

### 42.2 검증

- [x] 백엔드 11개 테스트 통과 (`test_k3s_master_ha.py`)
- [ ] 실 환경: master_count=3 클러스터 생성 → LB+FIP 자동 생성, server#2/3 join 확인
- [ ] 실 환경: server#1 강제 종료 → kubectl 페일오버 5초 내 확인
- [ ] 실 환경: master_count=2 요청 → 422 응답 확인

---

## § 43 — PR 3-A: k3s 인증서 만료 조회 + CA 다운로드 (2026-05-18)

### 43.1 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/app/services/k3s_certs.py` (신규) | `extract_ca_pem`, `parse_kubeconfig_certs`, `probe_tls_server_cert` |
| `backend/app/api/k3s/certificates.py` (신규) | `GET /{id}/ca-certificate`, `GET /{id}/certificate-expiry` |
| `backend/app/api/k3s/__init__.py` | `k3s_certificates_router` 등록 |
| `backend/app/main.py` | `k3s_certificates_router` import + `include_router` (service_k3s_enabled 가드) |
| `backend/app/models/k3s.py` | `CertificateInfo`, `CertificateExpiryResponse` Pydantic 모델 추가 |
| `backend/app/api/identity/admin.py` | 관리자 미러 2개: `GET /k3s-clusters/{id}/ca-certificate`, `GET /k3s-clusters/{id}/certificate-expiry` |
| `backend/tests/test_k3s_certs.py` (신규) | 13개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `CertificateInfo`, `CertificateExpiryResponse` 타입 추가 |
| `frontend/src/lib/components/k3s/K3sClusterInfoCard.svelte` | 인증서 행 (CA 다운로드 버튼 + 만료 조회 버튼) 추가 |
| `frontend/src/lib/components/k3s/K3sCertificateExpiryModal.svelte` (신규) | CA/클라이언트/서버TLS 만료 정보 모달 (days_remaining 색상 chip) |

### 43.2 검증

- [x] 백엔드 13개 테스트 통과 (`test_k3s_certs.py`)
- [x] ruff lint 클린
- [ ] 실 환경: `GET /api/k3s/clusters/{id}/ca-certificate` → PEM 다운로드 확인
- [ ] 실 환경: `GET /api/k3s/clusters/{id}/certificate-expiry` → days_remaining 정상 반환 확인
- [ ] 실 환경: TLS 프로브 가능한 클러스터에서 server_via_tls 배열 확인

---

## § 44 — PR 3-B: k3s 인증서 회전 자동화 (2026-05-18)

k3s 인증서 rolling 회전 — K8s Job(hostPID + nsenter)으로 SSH 없이 `systemctl restart k3s` 트리거.
k3s는 재시작 시 만료 90일 이내 인증서를 자동 갱신한다.

### 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/migrations/012_k3s_cert_rotation.sql` (신규) | `last_rotation_at`, `last_rotation_initiated_by` ALTER |
| `backend/app/models/db.py` | `K3sCluster.last_rotation_at`, `last_rotation_initiated_by` 컬럼 추가 |
| `backend/app/models/k3s.py` | `K3sProgressStep.ROTATE_DISCOVER/SERVER/AGENT/VERIFY` 추가 |
| `backend/app/config.py` | `k3s_cert_rotation_node_timeout_sec`, `k3s_cert_rotation_job_image` |
| `generate_k8s.py` | k3s_keys_str/int에 cert rotation 키 추가 |
| `config.toml.example` | [k3s] cert rotation 섹션 문서화 |
| `backend/app/services/k3s_kube.py` | `list_server_nodes`, `create_job`, `wait_job_completed`, `wait_node_ready` |
| `backend/app/services/k3s_db.py` | `record_rotation()` |
| `backend/app/services/k3s_cert_rotation.py` (신규) | `rotate_certificates()` 제너레이터, Redis 락, 캐시 무효화 |
| `backend/app/api/k3s/certificates.py` | `POST /{id}/rotate-certs` SSE 엔드포인트 추가 |
| `backend/app/api/identity/admin.py` | 관리자 미러: `POST /k3s-clusters/{id}/rotate-certs` |
| `frontend/src/lib/components/k3s/K3sCertificateExpiryModal.svelte` | "인증서 회전" 버튼 (HA 전용) |
| `frontend/src/lib/components/k3s/K3sRotateProgressModal.svelte` (신규) | SSE 스트림 진행률 모달 |
| `backend/tests/test_k3s_cert_rotation.py` (신규) | 12개 테스트 |

### 완료 기준

- [x] 백엔드 12개 테스트 통과 (`test_k3s_cert_rotation.py`)
- [x] PR 3-A 회귀 없음 (`test_k3s_certs.py` 13개 통과)
- [x] ruff lint 클린
- [ ] 실 환경: HA(3-master) 클러스터에서 회전 → SSE 스트림 완료, cert NotAfter 갱신 확인
- [ ] 실 환경: 단일 마스터 클러스터에서 회전 → 422 확인
- [ ] 실 환경: 동시 회전 → 두 번째 요청 409 확인

---

## Phase 48 — Frontend 공통 패턴 추출

### Phase 48a — SWR 헬퍼 추출

- [x] `frontend/src/lib/utils/swr.svelte.ts` 신규 생성 (`createSwr` 팩토리)
- [x] `volumesController.svelte.ts` 인라인 swrGet/swrSet → `createSwr` import
- [x] `dashboard/network/networks/+page.svelte` 인라인 swrGet/swrSet → `createSwr` import
- [x] `dashboard/compute/instances/+page.svelte` 인라인 swrGet/swrSet → `createSwr` import
- [x] `dashboard/file-storage/+page.svelte` 인라인 swrGet/swrSet → `createSwr` import
- [x] npm run check 62 errors (기존과 동일, 신규 없음)
- [x] npm run test 7 failed / 215 passed (기존과 동일, 신규 없음)

### Phase 48b — Controller 추출

- [x] `admin/database-instances/[id]` → `adminDatabaseInstanceDetailController.svelte.ts`
- [x] `dashboard/network/loadbalancers/[id]` → `networkLoadbalancerDetailController.svelte.ts`
- [x] `dashboard/loadbalancers/[id]` → `loadbalancerDetailController.svelte.ts`
- [x] `admin/quotas` → `adminQuotasController.svelte.ts`
- [x] `admin/groups` → `adminGroupsController.svelte.ts`

### Phase 48c — 인라인 타입 통합

- [x] `dashboard/topology/+page.svelte` 5개 인라인 타입 → `lib/types/topology.ts`
- [x] `Network`/`SubnetDetail` 중복 2곳 → `lib/types/networks.ts`
- [x] `Project`/`ProjectMember` → `lib/types/project.ts` (신규)
- [x] `PagedResponse<T>` → `lib/types/resources.ts` (기존)
- [x] `SecurityGroupRule`/`SecurityGroup` → `lib/types/securityGroup.ts` (신규)
- [x] `QuotaItem`/`ManilaFileQuota` → `lib/types/quotas.ts` 확장

### Phase 48d — ConfirmDialog 추출

- [x] `lib/components/ui/ConfirmDialog.svelte` 신규 (ESC 닫기 포함)
- [x] `lib/stores/confirm.svelte.ts` 신규 (`confirmDialog()` Promise<boolean>)
- [x] `+layout.svelte`에 `<ConfirmDialog />` 마운트
- [x] routes 31개 파일 42곳 `confirm()` → `await confirmDialog()` 치환
- [x] Phase 48b controller 3개 내부 `confirm()` 동일 치환

### Phase 48e — Modal/FormModal 추출

- [x] `lib/components/ui/Modal.svelte` 신규 (백드롭 + ESC 닫기)
- [x] `lib/components/ui/FormModal.svelte` 신규 (Modal 래핑, submit/cancel 슬롯)
- [x] `admin/floating-ips/+page.svelte` 인라인 백드롭 2곳 → `<Modal bind:open>` 교체
- [x] `admin/drover/templates/+page.svelte` 인라인 백드롭 1곳 → `<Modal>` 교체
- [x] npm run check 62 errors (기존과 동일)
- [x] npm run test 7 failed / 215 passed (기존과 동일)

### Phase 48 — 180줄 잔존 파일 예외 처리 (architect 검증 완료)

다음 5개 파일은 Phase 48b 명시 스코프(5개)에 포함되지 않았으며, architect 검토 결과 controller 추출 ROI 부족으로 **의도적으로 제외**:

| 파일 | 줄수 | 제외 사유 |
|---|---|---|
| `admin/volumes/+page.svelte` | 200 | modal 합성 컨테이너, template 98줄 고정 — 추출 가치 < 비용 |
| `admin/orphans/+page.svelte` | 193 | bind:selected 양방향 바인딩 4개, 추출 시 wrapping 오버헤드 |
| `admin/ports/+page.svelte` | 193 | Phase 49+ 후속 분리 검토 대상 |
| `dashboard/network/security-groups/+page.svelte` | 187 | bind:ruleForm 양방향 바인딩, Phase 49+ 검토 |
| `dashboard/network/networks/[id]/+page.svelte` | 185 | Phase 49+ 후속 분리 검토 대상 |

## Phase 49 — Frontend 후속 리팩토링 (UX 일관성 + 구조 개선)

### Phase 49a — confirm() 잔존 39건 confirmDialog 치환

- [x] lib/stores 14개 파일 (instanceDetail, dbInstanceDetail, loadBalancerDetail, routerDetail, fileStorageDetail, volumeDetail, volumesController, networkDetail, objectBrowser, k3sClusterDetail, imageDetail, k3sClusterListController, containerDetail, imagesController) confirm() → await confirmDialog()
- [x] lib/components 4개 (K3sClusterConfigMapsCard, K3sClusterSecretsCard, KeypairsSection, SystemAdminTable) confirm() → await confirmDialog()
- [x] grep confirm() 0건 확인
- [x] npm run check 62 errors baseline 유지
- [x] npm run test 7 known failures 외 회귀 없음

### Phase 49b — alert() 128건 toast 교체

- [x] lib/stores 14개 + lib/components 2개 alert() → toast.error/warning/success 치환
- [x] routes/ 29개 파일 alert() → toast.error/warning/success 치환
- [x] grep alert() 0건 확인
- [x] npm run check 62 errors baseline 유지
- [x] npm run test 7 known failures 외 회귀 없음

### Phase 49c — legacy dashboard/loadbalancers/new/ 삭제

- [x] +page.svelte + +page.server.ts 삭제 (진입 link 0건 사전 확인)
- [x] npm run check 62 errors baseline 유지

### Phase 49d — resources.ts 도메인 분리

- [x] 7개 중복 이름 단일 source 통합 (Network/NetworkDetail/SubnetDetail → networks.ts, SecurityGroup → securityGroup.ts, Quotas → quotas.ts DashboardQuotas, QuotaItem/PagedResponse → 각 도메인)
- [x] common.ts/compute.ts/volume.ts/loadbalancer.ts/database.ts/fileStorage.ts 도메인 파일 분리
- [x] 143개 import 업데이트 — from '$lib/types/resources' 잔존 0건

### Phase 49e — 11개 Detail store controller 컨벤션 정렬

- [x] 파일명 xxxDetailController.svelte.ts, factory createXxxDetailController
- [x] loadBalancerDetail 신·구 공존 해소

### Phase 49f — GlobalTopology.svelte 678줄 내부 분해

- [x] lib/components/topology/ 신규 (topologyHelpers.ts, topologyDerivedController.svelte.ts, TopologyHeader.svelte, TopologySidebar.svelte)
- [x] GlobalTopology.svelte ≤ 250줄 (241줄)

---

## Phase 50 — Anthropic Design Handoff 적용 (대시보드 4 + 관리자 4 페이지)

### Phase 50a — 디자인 토큰 + UI primitive 5종 신규

- [x] --admin-tone CSS 변수 추가 (layout.css dark/light)
- [x] Pill.svelte 신규 (8 tone)
- [x] SectionHeader.svelte 신규 (uppercase + meta + right slot)
- [x] Spark.svelte 신규 (SVG path, fixedWidth/stretch)
- [x] Donut.svelte 신규 (SVG strokeDasharray + center slot)
- [x] CapacityBar.svelte 신규 (80%/95% 자동 톤)
- [x] StatTile.svelte admin-tone accent 추가
- [x] lib/components/ui/index.ts barrel export 신규
- [x] npm run check baseline 유지 (59 errors ≤ 62 baseline)

### Phase 50b — 백엔드 endpoint (대시보드 4-A~4-E) + pytest

- [x] backend/app/api/dashboard/ 5개 endpoint
- [x] backend/app/models/dashboard.py Pydantic 모델
- [x] backend/tests/test_dashboard_*.py pytest
- [x] pytest 통과

### Phase 50c — 백엔드 endpoint (관리자 A-1~A-7) + pytest

- [x] admin_dashboard.py A-1~A-6 endpoint
- [x] admin_identity.py A-7 summary
- [x] bulk-action ActivityLog 자동 기록
- [x] backend/tests/test_admin_dashboard.py require_admin 거부 케이스 포함
- [x] pytest 통과

### Phase 50d — 사이드바 nav + 신규 라우트 3종 스켈레톤

- [x] Sidebar.svelte 대시보드 섹션 4개 메뉴
- [x] dashboard/usage, usage-report, activity 라우트 스켈레톤

### Phase 50e — 대시보드 4 페이지 마크업 이식

- [x] routes/dashboard/+page.svelte PageOverview 이식 (14d 추세 + 알림 섹션 추가)
- [x] routes/dashboard/usage/+page.svelte PageUsage 이식
- [x] routes/dashboard/usage-report/+page.svelte PageUsageReport 이식
- [x] routes/dashboard/activity/+page.svelte PageActivity 이식
- [x] 비용/요금 단어 0건

### Phase 50f — 관리자 4 페이지 마크업 이식

- [x] routes/admin/+page.svelte 알림 배너 + AutoRefresh 추가
- [x] routes/admin/identity/+page.svelte 허브 신설 (3탭 + admin-tone)
- [x] routes/admin/monitoring/+page.svelte Grafana 바로가기 9종 추가
- [x] routes/admin/instances/+page.svelte 5 KPI tiles 추가
- [x] AdminSidebar.svelte Identity 허브 링크 추가
- [x] bulk action ActivityLog 백엔드 검증 완료 (Phase 50c pytest)

### Phase 50g — 8 페이지 AutoRefresh 통합

- [x] 8 페이지 createAutoRefresh 적용 완료 (Phase 50e/50f에서 통합)
- [x] localStorage 키 분리 (dashboard-home/usage/usage-report/activity, admin-overview/identity/monitoring/instances)

### Phase 50h — milestone 정리 + 디자인 회귀 점검

- [x] 비용/요금 단어 0건 (dashboard/admin 전체)
- [x] 하드코딩 hex 0건 (4개 신규 대시보드 + 4개 관리자 페이지)
- [x] 신규 4 대시보드 페이지 OpenStack 서비스명 0건
- [x] npm run check baseline 59 errors 유지
- [x] milestone.md 50a~50h [x]

---

## Phase 51 — Phase 50 후속 프로덕션 버그 5건 수정

### Phase 51a — admin identity summary 500 fix

- [x] `_collect()` users/projects/roles 개별 try/except + partial 필드 반환
- [x] 외부 except에 `_logger.exception` 추가로 traceback 운영 가시화
- [x] pytest: 부분 실패 케이스 2종 추가 (test_admin_dashboard.py)

### Phase 51b — /dashboard/usage 무한 로딩 fix

- [x] 백엔드 응답 키 `volume_by_type` → `volumes_by_type` 통일
- [x] 프론트 `$effect` authReady 가드 추가 (activity 패턴 일관화)

### Phase 51c — ActivityLog 가시성 + db_status 노출

- [x] `services/activity.py` silent return → rate-limited warning (60s/1회)
- [x] `/api/dashboard/activity` 응답에 `db_status` 필드 추가
- [x] `hour_distribution` 응답 형식 단순 배열로 수정 (프론트 인터페이스 일치)
- [x] `dashboard/activity/+page.svelte` db_status=unavailable 안내 카드 표시
- [x] pytest: test_activity_silent_skip.py 신규 (3 cases)

### Phase 51d — 사용자용 notifications 분리 + 14d trend 안내 개선

- [x] 사용자 대시보드 `/api/admin/notifications` → `/api/dashboard/notifications` 교체
- [x] 백엔드 신규 endpoint: project-scoped ERROR 인스턴스 알림
- [x] 14d trend placeholder 문구 → "메트릭 수집 미설정 — 관리자에게 Grafana 설정 문의"
- [x] pytest: test_dashboard_notifications.py 신규 (3 cases)

### Phase 51e — /admin/monitoring Grafana 바로가기 섹션 제거

- [x] admin/monitoring/+page.svelte Grafana 섹션 삭제 (사이드바 9종과 완전 중복)
- [x] SectionHeader import 함께 제거

### Phase 51f — 검증

- [x] pytest 22 passed (test_admin_dashboard + test_dashboard_notifications + test_activity_silent_skip)
- [x] npm run check 59 errors baseline 유지

---

## Phase 52 — Phase 51 후속 프로덕션 버그 5건 수정 + 14d trend 실데이터 연결

### Phase 52a — /dashboard/usage TypeError fix (응답 키 정렬)

- [x] top_instances: `flavor` → `flavor_name`, `status`/`disk_gb`/`usage_hours` 추가
- [x] `_list_flavors_as_dicts` vcpus/ram/disk 필드 추가
- [x] `_list_servers_as_dicts` name/created_at 필드 추가
- [x] volumes_by_type: `size_gb` → `total_gb`, `count` 필드 추가
- [x] isGpu(inst.flavor_name) TypeError 해소

### Phase 52b — /dashboard/usage-report TypeError fix (forecast 키 정렬)

- [x] 응답 `quota.forecast_pct` → `forecast.{vcpu_pct, memory_pct, storage_pct}`
- [x] memory_pct/storage_pct 신규 계산 추가
- [x] test_dashboard_usage_report.py 신규 4케이스

### Phase 52c — /admin/identity 허브 "undefined" fix

- [x] 응답에 flat alias 추가 (user_count/project_count/role_count/group_count/domain_count)
- [x] recent_users/recent_projects 최근 5건 반환
- [x] Phase 51a partial 케이스 호환 유지
- [x] test_admin_dashboard.py Phase 52c 케이스 추가

### Phase 52d — k3s 클러스터 상세 namespace 자동 로드

- [x] K3sClusterDetailPanel.svelte: ACTIVE 진입 시 loadNamespaces() 자동 호출
- [x] ConfigMap/Secret CRUD 네임스페이스별 동작 가능

### Phase 52e — 14d trend 카드 PromQL 실데이터 연결

- [x] /api/dashboard/metrics/trend endpoint 신규 (PromQL range_query, 14일치 1일 step)
- [x] Prometheus 미설치 시 prometheus_available=false + data=[] fallback (500 없음)
- [x] dashboard/+page.svelte Spark 컴포넌트 실데이터 연결
- [x] prometheus_available=false 시 observability 링크 포함 안내 표시
- [x] test_dashboard_metrics.py 신규 4케이스

### Phase 52f — 검증

- [x] pytest 41 passed (test_dashboard_new + test_dashboard_usage_report + test_dashboard_metrics + test_admin_dashboard + test_activity_silent_skip + test_dashboard_notifications)
- [x] npm run check 59 errors baseline 유지

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
