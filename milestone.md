# Union 프로젝트 마일스톤

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
