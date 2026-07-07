# Changelog

이 프로젝트의 모든 주요 변경사항은 이 파일에 기록됩니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 1.1.0 을 따르며,
프로젝트는 [SemVer](https://semver.org/lang/ko/) 2.0.0 을 따릅니다.

## [1.16.0] - 2026-07-07

### Added

- **브라우저 로컬 베타 기능 관리 확장** — 계정 설정의 베타 토글을 Key Manager, 볼륨 백업/스냅샷, 파일 스토리지 스냅샷·Share Network·Security Service, DB 백업까지 확장하고 `localStorage` 기반 브라우저별 선호를 유지.
- **베타 기능 게이트 컴포넌트** — 비활성화된 베타 화면에서 계정 설정으로 이동하는 공통 안내 UI를 추가해 아직 검증 중인 기능의 진입점을 일관되게 차단.
- **베타 게이트 회귀 테스트** — 베타 store, 계정 토글, 공통 게이트, 내비게이션 소스 계약, 볼륨 요약 카드 조건부 렌더링을 테스트로 고정.

### Changed

- **내비게이션 베타 필터링** — Sidebar, AdminSidebar, Command Palette가 비활성 베타 항목을 숨기도록 통합 필터를 적용.
- **고위험 기능 기본 비활성화** — Key Manager, 볼륨 백업/스냅샷, 파일 스토리지 스냅샷·Share Network·Security Service, DB 백업의 목록·상세·생성 흐름을 명시적으로 켠 브라우저에서만 노출.

## [1.15.2] - 2026-06-15

### Security

- **cloud-init export 값 인젝션 방어** — `union_ro_share_export`/`union_manifest_share_export`를 화이트리스트 정규식으로 검증해 cloud-init YAML 구조 주입(임의 write_files/runcmd)을 차단. 형식 검증 정규식의 종단 앵커를 `$` → `\Z`로 교정해 trailing-newline 우회까지 차단.
- **union `get_dependents` IDOR 방어** — 부모 레이어 소유권을 진입부에서 우선 검증하고, 공유 부모의 자식 중 타 프로젝트 소유 레이어를 응답에서 필터링.
- **`secret_key` 엔트로피 게이트** — 비기본이어도 32자 미만이면 `AFTERGLOW_ENV=production` 부팅을 거부(dev는 경고).
- **에러 응답 내부정보 노출 차단** — `openstack_error_to_http`가 5xx에서 OpenStack 내부 URL/메시지를 일반 메시지로 치환(관리자에게만 원문). 깨진 `http_status`→`status_code` 속성 버그도 교정.
- 라이브러리 카탈로그 `is_admin` 키 오타 수정(`is_system_admin`).

### Added

- **GPU 진단 엔드포인트** `GET /api/admin/gpu-hosts/raw` — 오디오 필터 미적용 실 device_id/vendor_id 노출.
- **인스턴스 일괄 선택/액션** — `POST /api/instances/bulk-action`(화이트리스트·max 50·per-id IDOR·부분성공) + 관리자 목록 일괄 액션, 상태 전이 시 autoRefresh 가속.
- **ERROR 인스턴스 복구** — 자동 진단(안전 검사 5종) + 시나리오별 복구 추천 + 관리자 확인 후 원클릭 실행.
- **인스턴스 리소스 사용량 통계**(min/avg/max) + 7일 저사용 리사이즈 권장.
- **GPU 카탈로그 DB화** + 엑셀/CSV 템플릿 다운로드·업로드, flavor 속성 템플릿, 하이퍼바이저-GPU 페이지 통합(+ GPU 모델 컬럼).
- **인스턴스 마이그레이션** — CPU 호환 호스트 필터링 + 마이그레이션 추적 + 라이브 제어.
- **라이브러리 레시피 모듈화** — 범용 빌딩 블록 + apt 스택 레이어, NFS/CephFS 파일 스토리지 직접 마운트.
- **Helm GPU 디바이스 맵 오버라이드**(`gpu.configToml`) + `config2helm.py` 동기화.
- **작업 기록 체계 OpenSpec 도입** — 단일 `milestone.md`를 `openspec/changes/`(진행)·`changes/archive/`(완료)로 분할·이관.

### Changed

- **쿼터 데이터 소스 통합** — 쿼터 카드/타일을 `/api/dashboard/summary` → `/api/dashboard/quotas`로 전환(중복 OpenStack API 호출 제거).
- **문서 정비** — README 간결화 + 문서 사이트 안내, `milestone.md` → OpenSpec 이관(redirect stub).

### Fixed

- **인스턴스 페이지 SSR 500** 3가지 원인 수정.
- **스토리지** — 접근 규칙 생성 실패 3종, NFS share type proto별 fallback + 409 노출, DHSS=False share network 처리, 생성 마법사 단계 스킵.
- **인증** — 탭 간 세션 동기화 + 깨진 401 refresh 복구 경로, `/api/libraries/file-storages` 인증 추가(비인증 export_locations 노출 차단).
- **UX** — GPU quota 카드 깜빡임 제거, 개요 카드 호버 통일, openpyxl 미설치 시 xlsx 다운로드 안내.
- **배포** — backend startupProbe 한도 5분 → 20분 확대, 마이그레이션 `ValidationError` 수정.

## [1.15.1] - 2026-06-11

### Security

- **cloud-init/SSH 보간 값 쉘·YAML 인젝션 방어 강화** — Manila/Keystone 등 외부 API 반환값(export_path, cephx_user 등)도 신뢰하지 않고 `shlex_quote` 쿼팅. cloud-init YAML 개행 주입 차단 검증 추가.

### Added

- **Helm 차트 (`helm/afterglow`)** — 기존 Kustomize + `generate_k8s.py` 2단계 배포를 values 기반 단일 차트로 통합. 18개 리소스(backend/frontend/worker/redis HA/ingress/middleware) + 선택적 모니터링 스택(grafana/prometheus/opensearch, 기본 비활성).
- **ArgoCD Helm 추적 전환** — `argocd/generate_helm_application.py`로 git 미추적 values 파일을 Application `valuesObject`로 인라인. Image Updater는 helm parameter(digest 전략)로 전환, worker 이미지도 자동 추적 추가.
- **config2helm.py** — 기존 `config.toml`을 Helm values 파일로 변환하는 마이그레이션 스크립트.
- **Redis Sentinel HA** — 캐시 백엔드 Sentinel 모드 지원 (`sentinel_enabled`/`sentinel_hosts`). K8s에서 redis StatefulSet + sentinel 3노드 구성.
- **라이브러리 빌더 사전 생성 share 경로** — `existing_share_id`로 기존 Manila share 재사용 빌드 지원 + python311 E2E 테스트.
- **버전 관리 정책 문서(VERSIONING.md)** 및 보안 개발 가이드라인(CLAUDE.md) 추가.

### Fixed

- **빌더 안정화** — python311 빌드 타임아웃 + NFS 병렬 복사, SHUTOFF 후 console 미지원 환경 early sentinel fallback, poweroff 전 60초 대기로 sentinel 조기 감지 윈도우 확보, DB 비가용 시 ephemeral 빌드 진행 및 빌트인 레시피 fallback, build_id 직접 반환.
- **Manila** — `update_share_metadata` body 키 수정(`set_metadata` → `metadata`), prebuilt share 조회 시 public share(타 프로젝트 소유) 포함, 중복 시 최신(`union_built_at`) 우선 선택.
- **프론트엔드 로그인 안정화** — 로그인 직후 취소 요청 폭증·컴포넌트 이중 마운트 수정, 로그인창⇄대시보드 무한 진동 수정.
- **K8s Redis 네임스페이스 버그** — redis ClusterIP 서비스가 master(redis-0)만 타겟하도록 수정, replica/sentinel 설정의 네임스페이스 하드코딩을 상대 이름으로 변경(dev 네임스페이스 sentinel이 prod 호스트를 바라보던 문제 해소).
- **E2E 테스트** — JWT 만료 시 자동 재로그인, SSH 타임아웃 600초 확대, consumer VM keypair 지정, `AFTERGLOW_SKIP_SSH=1` 조건부 건너뜀.

---

## [1.15.0] - 2026-06-09

### Security — 전수 보안 감사 (milestone #69)

- **[CRITICAL] k3s nodegroup 명령 주입 차단** — `labels`/`taints`에 K8s 문법 Pydantic validator 추가. stampede reconciler 경유 root cloud-init RCE 차단. shlex_quote 전면 적용.
- **[CRITICAL] 계정 잠금 서브시스템 신규** — Redis 기반 `(username, domain)` 실패 카운트·지수 백오프·일시 잠금. 관리자 해제 엔드포인트(`POST /admin/users/unlock-account`) 추가.
- **[HIGH] JWT 경로 idle 세션 타임아웃 적용** — `_resolve_jwt_token_info` + `/refresh` 엔드포인트에 세션 타임아웃 검증 연결.
- **[HIGH] GitLab OIDC nonce 검증 추가** — authorize URL에 nonce 포함, callback에서 id_token 클레임 검증. 토큰 재생 공격 차단.
- **[HIGH] X-Auth-Token 레거시 인증 경로 제거** — 바인딩·블랙리스트를 우회하는 X-Auth-Token 경로 전면 제거. Bearer JWT 단일 인증으로 통일.
- **[MEDIUM] token-binding fail-closed 전환** — 바인딩 검사 예외 시 401 반환. 알 수 없는 binding mode 설정 시 시작 거부.
- **[MEDIUM] 기타** — SD 토큰 `hmac.compare_digest` 적용, 세션 소유권 이중 검증, 이메일 HTML 인젝션 방어, Trove 로그 비밀번호 redact.
- **admin_legacy_project_policy 기본값 False** — system:all 스코프만 시스템 관리자 인정. `backend/scripts/bootstrap_system_admin.py` 마이그레이션 CLI 신규.

### Added

- **세션 기기정보 표시** — 로그인 기기 타입·OS 세션 목록 표시. 개별 세션 삭제 지원.
- **관리자 사용자 목록 강화** — 검색·정렬·필터·통계 카드(전체/활성/비활성)·최근 변경 로그 추가.
- **토큰 출처 바인딩** — IP + 기기 지문 기반 토큰 바인딩. 블랙리스트·전체 로그아웃·Keystone 직접 폐기 지원.
- **활동 로그 미들웨어** — CRUD 자동 로깅 미들웨어 도입. 프로젝트 상세 GET 엔드포인트 추가.
- **DB 백업 관리 페이지** — APScheduler cron 스케줄링 + 복원 모달 UI.
- **federated 사용자 패스워드 변경 카드 숨기기** — OIDC/외부 로그인 사용자에게 비밀번호 변경 UI 미노출.

### Fixed

- **trusted_proxies 기본값 복원** — loopback 전용(`127.0.0.1/32,::1/128`)으로 복원. Docker 프록시 설정 가이드 추가.
- **DB 백업 타임아웃 false-negative 교정** — 백업 생성 타임아웃 오감지 수정 + 에러 노출 개선.
- **프론트엔드 이름 버튼 hover 색상 복구**.
- **모바일 헤더 정리** — 스탯 타일 3개·breadcrumb 단축·페이지 크기 고정.
- **모바일 목록 이름 컬럼** — 화면 폭 2/3 제한·말줄임 처리.
- **쿼터 한도 안내** — 쿼터 초과 메시지를 관리자 문의로 변경.

### Changed

- **캐시 기본값 OFF** — 캐시 opt-in(`?cache=true`) 방식 전환. write-through/patch_list 헬퍼 추가.
- **프론트엔드 포트 3080** — Docker/Kubernetes/Kolla 전반 프론트엔드 포트 3000 → 3080 통일. K8s deployment(containerPort, PORT env, 3개 probe), Service, Ingress, ConfigMap, docker-compose.prod, kolla defaults, generate_k8s.py, config.py 기본값 모두 갱신.
- **이름 셀 클릭 영역 확장** — 아이콘+텍스트+빈공간 전체로 확장.

---

## [1.14.7] - 2026-06-04

### Added

- **Notion 자동 동기화 워커** — 주기적 Notion 동기화를 담당하는 경량 독립 워커 컨테이너 추가. 기본 간격 30분, `afterglow-worker` 이미지로 분리 배포.

### Fixed

- **Notion 워커 timezone 버그** — MySQL naive datetime 비교 시 TypeError 묵살로 매 60초마다 재동기화되는 문제 수정.
- **Notion 워커 DB 연결** — `settings.database` → `settings.database_url` (flat 키), `await init_db` → `init_db` (동기) 수정.
- **Notion 동기화 시각 표시** — 프론트엔드에서 UTC 문자열 대신 현지 시각으로 표시.
- **빌드 현황 테이블** — sticky 헤더의 `border-collapse` 충돌로 스크롤 시 구분선이 사라지는 문제 및 긴 `library_id`로 인한 수평 스크롤바 유발 수정.

### Changed

- **빌드 현황 UI** — 테이블 높이를 `max-h-80`으로 제한하고 내부 스크롤 추가. 목록이 많아도 페이지가 길어지지 않음.
- **목록 행 클릭 UX** — 행 전체 클릭 → 이름 영역(링크)만 상세 이동으로 통일. 체크박스·액션 버튼과의 클릭 충돌 제거.

### Dependencies

- `vitest` 3 → 4, `@vitest/coverage-v8` 3 → 4 (메이저 업그레이드, 237 테스트 통과).

---

## [1.14.1] - 2026-05-09

### CI / 인프라

`v1.14.0` release pipeline 이 두 단계에서 fail 하여, 동일 보안 패치 + workflow
fix 를 묶은 정식 release 로 1.14.1 발행.

- **`Apply tag version` 스텝의 npm not found** (PR #18) — `docker-build.yml` 에
  tag push 일 때만 `actions/setup-node@v4` 추가
- **arm64 self-hosted macos runner 의 uv cache lock race** (PR #19) —
  backend/frontend 두 잡이 동일 `~/.cache/uv/.lock` 동시 접근 → 300s timeout.
  `astral-sh/setup-uv` 의 `enable-cache` 를 `${{ matrix.arch == 'amd64' }}` 로
  분기 (linux runner 별도 인스턴스만 캐시).

`v1.14.0` 의 ghcr 이미지 (`-amd64`/`-arm64` single-platform 만 푸시되고
멀티아치 manifest 미생성) 는 broken release 로 두고 1.14.1 을 정식 사용.

보안 패치 내용은 1.14.0 과 동일 (PR #17). 상세는 아래 참조.

---

## [1.14.0] - 2026-05-09 (broken release)

> ⚠️ 이 release 는 CI pipeline fail 로 ghcr 의 멀티아치 `:v1.14.0` manifest 가
> 만들어지지 않은 broken release 입니다. 동일 변경사항을 1.14.1 로 재발행했으니
> [1.14.1](#1141---2026-05-09) 을 사용하세요.

### 보안 (Security) — PR-A + PR-B (2차 보안 패치)

1차 PR (Critical 5 + High 13) 후 잔존 취약점 전수 조사로 식별된
신규 Critical 5 + High 7 + Medium 11 + Low 9 중 최우선 카테고리 처리.

#### Defense-in-depth IDOR 가드

OpenStack RBAC (project-scoped Keystone token) 이 1차 방어선이지만, policy 가
광범위하거나 admin 토큰 누설 시 백엔드에서 한번 더 차단하도록 `assert_resource_owner`
헬퍼를 mutation/detail 엔드포인트에 일관 적용.

- **Network/Router/SG/FIP/Subnet** — `GET`/`DELETE`/`UPDATE` (외부·공유 네트워크 면제)
- **Loadbalancer** — LB/listener/pool/member/health-monitor (lb_id sub-path 모두)
- **Database (Trove)** — instance/databases/users/backups + restore from backup;
  특히 `enable_root_user` (root password 발급) cross-project 차단
- **Storage (Cinder)** — volume/snapshot/backup + transfer endpoint
- **Object Storage** — 신규 컨테이너 생성 시 `X-Container-Meta-Owner-Project-Id`
  자동 부착 (Swift account 모델이 1차 방어, metadata 는 운영 도구 토대)
- **File Storage (Manila)** — share access-rule (list/grant/revoke) 의 owner 검증
  비대칭 해소 — 다른 프로젝트 share 에 IP rule 추가로 cross-tenant CephFS mount
  가능했던 케이스 차단

#### K3s 보안 강화

- **Kubeconfig 다운로드 audit log** — 매 GET 마다 `audit_log.rec(action="kubeconfig_download")`
  + source IP 기록. 토큰 탈취 시 forensic 추적 가능.
- **Callback source IP 로깅** — `_get_real_ip` (1차 PR 의 `trusted_proxies` 검증)
  으로 추출한 source IP 를 callback 로그에 기록. body.server_ip 와 불일치 시 warning.
- **HKDF v3 sub-key 도메인 분리** — 단일 마스터키로 4종 데이터
  (kubeconfig / node_token / notion / manager_password) 를 암호화하지만,
  HKDF-SHA256 으로 도메인별 sub-key 파생 → cross-domain decrypt 불가 (key separation).
- **v2/legacy ciphertext fallback 유지 + deprecation warning** — 다음 PR 에서
  마이그레이션 스크립트와 함께 제거 예정.

#### Health Bearer 토큰 lifetime

- `_TOKEN_TTL`: **30일 sliding → 7일 절대 만료**. 이전엔 매 호출마다 TTL 갱신되어
  사실상 영구 토큰이었음 — VM userdata 노출 시 무기한 cephx rotate 권한.
- 7일 이상 살아있는 인스턴스는 health_check.sh 가 자동 재발급.

### 변경 (Changed)

- `backend/tests/conftest.py` — `mock_conn` fixture 가 SDK `get_*` 응답을
  caller-owned 자원으로 default stub. cross-project 거부 테스트는 `.return_value`
  override 로 작성.

### 검증

- 단위 테스트: **1247 passed, 20 skipped**
- ruff lint + format check: 모두 통과
- advisor 검토 반영: object-storage 검증은 metadata 부착만 (회귀 회피),
  kubeconfig redemption URL 신설 제외 (URL artifact leak 회피),
  v2/legacy crypto 즉시 제거 회피 (배포 사고 방지)

### 마이그레이션 가이드

이 릴리스는 backward-compatible 입니다. 기존 v1/v2 ciphertext 는 자동으로
복호화되며 deprecation warning 만 로그에 1회 (도메인 단위) 기록됩니다.
신규 암호화는 모두 v3 prefix.

다음 릴리스에서 v2/legacy fallback 이 제거되므로 그 전에 마이그레이션 스크립트
(별도 PR 제공 예정) 로 batch re-encrypt 권장.

### 범위 외 (후속 PR 예정)

- PR-C: background task token lifetime + cephx rotate race lock
- PR-D: Frontend localStorage 토큰 → HttpOnly cookie + CSP nonce
- PR-E: K8s securityContext + NetworkPolicy + digest pin + HAProxy non-root
- PR-F: CI scanning (bun audit / pip-audit / trivy) + dependabot
- PR-G: Manila CSI application credential + extend-session CSRF + WebSocket subprotocol
- PR-H: Low 항목 일괄 (SECRET_KEY 엔트로피, Grafana JWT TTL, SecretStr 등)
- v2/legacy crypto fallback 제거 + 마이그레이션 스크립트

상세: [docs/releases/v1.14.0.md](docs/releases/v1.14.0.md), [docs/security.md](docs/security.md)

---

## [1.13.9] - 2026-05-07 이전

이 릴리스 이전 변경사항은 [git tag history](https://github.com/openstack-afterglow/openstack-afterglow/tags)
와 commit log 를 참고하세요. CHANGELOG 정식 운영은 1.14.0 부터 시작합니다.
