# Changelog

이 프로젝트의 모든 주요 변경사항은 이 파일에 기록됩니다.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 1.1.0 을 따르며,
프로젝트는 [SemVer](https://semver.org/lang/ko/) 2.0.0 을 따릅니다.

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

이 릴리스 이전 변경사항은 [git tag history](https://github.com/jung-geun/openstack-afterglow/tags)
와 commit log 를 참고하세요. CHANGELOG 정식 운영은 1.14.0 부터 시작합니다.
