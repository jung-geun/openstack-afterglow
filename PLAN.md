# Union: OpenStack VM 배포 + OverlayFS 마운트 웹 플랫폼

## Context

운영 중인 OpenStack 환경(Nova, Cinder/Ceph, Manila/CephFS, Keystone)에서 VM을 배포할 때, 원하는 OS 이미지를 선택하고 필요한 라이브러리(Python, PyTorch, vLLM, Jupyter)를 선택하면 Manila share에 마운트하고 OverlayFS로 합성해서 부팅하는 웹 플랫폼. 두 가지 라이브러리 전략(사전 빌드 공유 share / 동적 생성)을 모두 지원.

## 기술 스택

- **Frontend**: SvelteKit + TypeScript
- **Backend**: FastAPI (Python) + openstacksdk
- **OpenStack**: Nova, Cinder(Ceph), Manila(CephFS), Keystone

---

## 프로젝트 구조

```
union/
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
