# Afterglow — Claude Code 개발 규정

## 브랜치 전략

| 브랜치 | 용도 | 관리자 |
|--------|------|--------|
| `main` | 프로덕션. 배포 기준 버전 | pie_root (수동 PR/머지) |
| `dev`  | 개발. 모든 AI 개발 작업 대상 | Katherine (AI 에이전트) |

> **규칙**: 반드시 `dev` 브랜치에서만 작업한다. `main` 브랜치에 직접 커밋하지 않는다.
> PR과 `dev → main` 머지는 pie_root가 수행한다.

---

## 개발 워크플로우

Claude Code는 **인터랙티브 모드**(plan 모드 포함)와 **하네스(비인터랙티브 모드)** 두 가지로 실행될 수 있다.
인터랙티브 모드에서는 plan 모드를 사용하여 설계를 먼저 확정한 뒤 구현으로 진행한다.
하네스 모드(`--print`)로 실행될 때는 아래 단계를 순서대로 따른다.

### 단계 1 — Discord에서 플래닝 (Katherine 직접 수행)

개발 착수 전, Discord `#katherine` 채널에서 pie_root와 함께 다음을 확정한다:

1. **목표 명세**: 구현할 기능 또는 수정할 버그를 한 문장으로 정의
2. **범위 확정**: 수정 대상 파일/모듈 목록
3. **설계 결정**: 아키텍처 선택지, 트레이드오프 논의
4. **완료 기준**: 성공 여부를 판단할 조건 (테스트, 동작 확인 등)
5. **제약 조건**: 건드리지 않을 코드, 유지해야 할 호환성

플래닝이 완료되면 **Katherine이 구체적인 태스크 명세를 작성**하고 pie_root의 승인을 받은 후 단계 2로 진행한다.

### 단계 2 — 하네스 실행 (Katherine이 Claude Code 호출)

```bash
cd ~/code/openstack-afterglow
git checkout dev
git pull origin dev

claude --permission-mode bypassPermissions --print '[플래닝에서 확정된 태스크 명세]'
```

### 단계 3 — 결과 보고

하네스 실행 완료 후 Katherine이 Discord에 보고:
- 변경된 파일 목록
- 커밋 메시지
- 미완료 항목 또는 이슈

### 단계 4 — PR (pie_root 수행)

pie_root가 변경 내용 검토 후 `dev → main` PR을 직접 생성하고 머지한다.

---

## 태스크 명세 작성 형식

하네스에 전달하는 프롬프트는 아래 형식으로 작성한다:

```
[목표]
<한 문장 목표>

[현재 상태]
<관련 파일 경로와 현재 동작>

[요구 사항]
- <구체적 요구 사항 1>
- <구체적 요구 사항 2>

[제약]
- dev 브랜치에서만 작업
- <기타 제약>

[완료 기준]
- <확인 방법>
```

---

## 프로젝트 구조 요약

```
backend/              FastAPI + openstacksdk (Python 3.12+)
  app/api/            OpenStack 서비스별 라우터
    k3s/              k3s 클러스터 프로비저닝 API
    union/            Union Mount 레이어 API (신규)
  app/services/       OpenStack 클라이언트 래퍼
    k3s_plugins/      Cloud Provider OpenStack 플러그인 레지스트리
  app/models/         Pydantic 모델
  app/templates/      cloud-init Jinja2 템플릿
  tests/              pytest 단위 테스트 (엔드포인트별 의무)

frontend/             SvelteKit + TypeScript + Tailwind CSS 4
  src/routes/         페이지 라우터
  src/lib/
    components/       UI 컴포넌트 (AutoRefreshControl 등)
    utils/            유틸리티 (autoRefresh.svelte.ts 등)
    stores/           Svelte stores (auth, projectNames 등)
    api/              API 클라이언트

union.md              Union Mount 레이어 시스템 v2 설계 문서 (참조 필수)
openspec/             작업 기록 (OpenSpec) — changes/<slug>/ 진행 중, changes/archive/ 완료
milestone.md          → openspec/로 이관됨 (redirect stub만 유지)
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI 0.125, Python 3.12, openstacksdk 3.3 |
| Frontend | SvelteKit 2.50, Svelte 5, Tailwind CSS 4 |
| DB/Cache | SQLAlchemy 2.0 (asyncio) + asyncmy, Redis 7 |
| 특화 기능 | k3s 프로비저닝, Content-addressable OverlayFS 레이어, AES-256-GCM kubeconfig |
| 스토리지 | CephFS via Manila (layer-store-rw / layer-store-ro / manifest-store 3개 share) |

---

## 개발 규칙

### 테스트 의무

- **백엔드 엔드포인트를 구현하면 반드시 `backend/tests/` 에 pytest 테스트를 함께 작성한다.**
- 테스트 없는 엔드포인트 구현은 미완료로 간주한다.

#### 커밋 전 필수 검증 절차 (반드시 순서대로 실행)

```bash
# 1. 전체 테스트 + lint 실행
npm run test:all
npm run lint:backend

# 2. 위 명령이 모두 0(success) 으로 종료된 경우에만 커밋·push 진행
git add <변경 파일>
git commit -m "type: 요약"
git push origin dev
```

> **규칙**: 테스트나 lint 중 하나라도 실패하면 **커밋하지 않는다.**
> 실패 원인을 먼저 수정하고 재실행 후 전부 통과된 상태에서만 커밋한다.

### 작업 기록 의무 (OpenSpec)

작업 기록은 [OpenSpec](https://github.com/Fission-AI/OpenSpec)로 관리한다. 구 `milestone.md` 단일 파일 방식은 폐지되었고, 완료분은 `openspec/changes/archive/<날짜-슬러그>/`로 이관됐다.

- **신규 작업 착수 전**: `/opsx:propose "<목표>"`로 change를 만들고 `proposal.md`(목표·범위) + `tasks.md`(체크리스트)를 채운다. (CLI: `openspec new change <slug> --schema rapid`)
- **작업 중**: 완료 항목을 `openspec/changes/<slug>/tasks.md`에서 `[ ]` → `[x]`로 갱신한다.
- **작업 완료 시**: `/opsx:archive`로 아카이브한다. (CLI: `openspec archive <slug> --skip-specs --yes` — 본 프로젝트는 specs 레이어를 두지 않으므로 `--skip-specs` 필수. 현재 기능 명세는 `docs/` + `union.md`가 담당한다.)
- 기본 스키마는 tasks-only `rapid`(`openspec/config.yaml`의 `defaultSchema`). 현황은 `openspec list`로 확인한다.
- OpenSpec 슬래시 커맨드/스킬(`.claude/`)은 git-ignore되므로 머신별로 `openspec init`(또는 `openspec update`)를 1회 실행해야 한다. 커밋되는 것은 `openspec/`(changes·archive·schemas·config.yaml)다.

### 설정 파일 동기화 의무

> `afterglow.conf`가 신규 기본 설정 파일명이다(TOML 문법 유지). `config.toml`/`afterglow.toml`은 기존 배포
> 호환을 위해 `backend/app/config.py`가 계속 읽어들이지만, 예시/문서화 파일은 `afterglow.conf.example`
> 하나만 유지한다(`config.toml.example`은 제거됨 — 재생성 금지).

**`afterglow.conf` 항목 추가·변경 시 반드시 함께 갱신:**
- `backend/app/config.py` — `_load_toml()` flat dict + `Settings` 클래스 필드
- `generate_k8s.py` — 비밀 값은 `render_secret()`, 일반 값은 `_render_toml_for_k8s()`
- `afterglow.conf.example` — 새 항목을 예시/주석과 함께 문서화

**`backend/app/config.py` 필드 추가·변경 시 반드시 함께 갱신:**
- `generate_k8s.py` — K8s 배포 시 configmap 또는 secret에 포함되도록
- `afterglow.conf.example` — 해당 TOML 키가 예시 파일에 존재하도록

> 비밀 값(password, secret, token, key) 기준: `render_secret()` → secret.yaml 환경변수로 주입.
> 나머지는 `_render_toml_for_k8s()` → configmap의 afterglow.conf 인라인에 포함.

### API 버전 규칙

> **모든 라우터는 `/api/v1` 단독 마운트**로 전환 완료(2026-06-18).
> 레거시 `/api`는 아래 3종 baked 엔드포인트에 한해 dual-mount로만 유지한다. 신규 레거시 추가 금지.

**레거시 `/api` 유지 대상 (cloud-init baked — 기존 VM 재배포 없이 재bake 불가):**
- `POST /api/k3s/callback` → `k3s_callback_router` dual-mount
- `POST /api/instances/{id}/health/report` → `instance_health_router` dual-mount
- `POST /api/instances/{id}/credentials/rotate-cephx` → `instance_health_router` dual-mount

**규칙:**

1. **라우터 마운트는 `/api/v1` 단독.** `backend/app/main.py`의 `app.include_router(...)` 호출 시 `prefix="/api/v1/<resource>"` 형태를 사용한다.
   개별 라우터 파일(`APIRouter()`)은 prefix 없이 작성하고, 마운트 prefix는 `main.py` 등록 시점에서만 부여한다.
   baked 엔드포인트가 아닌 경우 레거시 `/api` 추가 dual-mount 금지.

   ```python
   # main.py 예시 — 신규 라우터 (v1 단독)
   app.include_router(my_new_router, prefix="/api/v1/my-resource", tags=["my-resource"])
   ```

2. **프론트엔드·테스트·배포 설정 모두 v1.** 모든 API 호출은 `/api/v1/...` 경로로 작성한다.
   테스트(`backend/tests/`)도 `/api/v1/...` 경로로 작성한다.
   k8s probe, haproxy healthcheck, prometheus configmap도 v1 기준.

3. **인가/리소스 매핑 동기화 의무.** v1 엔드포인트가 소유권 검증 대상 리소스를 다루는 경우,
   `main.py`의 `_AUDIT_PREFIX_MAP` 리스트에 `/api/v1/<resource>` 항목을 **반드시 함께 등록**한다.
   이 매핑이 빠지면 fail-closed 감사 미들웨어가 조용히 무력화된다.

   ```python
   # main.py _AUDIT_PREFIX_MAP 예시 — 신규 v1 리소스
   ("/api/v1/my-resource", "my_resource"),
   ```

4. **baked 레거시 계약 테스트.** `backend/tests/test_api_v1_legacy_compat.py`가 3종 baked 경로의
   `/api` 레거시 dual-mount 존재를 고정(404 아님)한다. 이 테스트를 삭제하거나 무력화하지 않는다.

### Union Mount 설계

- Union Mount 레이어 시스템 구현 시 **`union.md` 를 반드시 먼저 읽는다.**
- Content-addressable 레이어, single-parent 상속, 3-lock 불변성 등 설계 원칙을 따른다.

---

## 보안 개발 가이드라인

> 이 프로젝트는 cloud-init/SSH로 **root 권한 원격 실행**을 수행하고 OpenStack 멀티테넌트
> 리소스를 다룬다. 아래 규칙은 의무이며, 신규 코드 작성·리뷰 시 반드시 점검한다.
> 전수 감사 방법론은 `security-audit` 스킬을 참조한다.

### 1. 쉘·cloud-init·템플릿 보간 (명령 주입 방어)

- SSH 원격 명령, cloud-init user-data, Jinja2 템플릿에 들어가는 **모든 동적 값**은
  쿼팅한다. Python은 `shlex.quote()`, Jinja2 템플릿은 `| shlex_quote` 필터.
- **외부 시스템(Manila/Keystone/Nova 등 OpenStack API) 반환값도 신뢰하지 않는다.**
  export_path·cephx_user 등 API 응답도 공격자가 영향을 줄 수 있다고 가정하고 쿼팅한다.
- 참조 구현: `app/services/ephemeral_mount.py:build_mount_command`,
  `app/services/cloud_init_builder.py:_render_mount_lines`,
  `app/services/cloudinit.py`(Jinja2 env에 `shlex_quote` 필터 등록, `autoescape=False`).

### 2. 입력 검증 (화이트리스트 + 출력 쿼팅 이중 방어)

- 사용자/외부 입력이 실행 컨텍스트(cloud-init YAML, K8s 라벨/테인트, 쉘)에 도달하면
  **Pydantic validator로 화이트리스트 정규식 검증** 후, 출력 시 다시 쿼팅한다.
- cloud-init YAML에 보간되는 값은 **개행 주입(YAML 구조 파괴 → 임의 write_files/runcmd)**
  을 막기 위해 형식을 검증한다. 참조: `app/services/cloudinit.py:_validate_cloudinit_inputs`
  (cephx_id/cephx_key/ceph_monitors), `app/models/k3s.py`(nodegroup labels/taints validator).

### 3. fail-closed 원칙

- 보안 검사(토큰 바인딩, 세션 블랙리스트, 리소스 소유권)는 예외 발생 시 **요청을 거부**한다.
  `except Exception: pass` 또는 `logging.warning` 후 통과는 금지. 참조:
  `app/api/deps.py`의 토큰 바인딩 검사(`fail-closed`, Redis 장애 시 401).
- **예외**: 로그인 계정 잠금(`app/services/login_guard.py`)은 가용성 우선으로 fail-open(Redis
  장애 시 잠금 생략)으로 **의도적으로 결정**됨. 이 동작은 변경하지 말고, 변경이 필요하면 사전 협의.

### 4. 타이밍 안전 비교

- API 토큰·다운로드 토큰·HMAC 서명·웹훅 시크릿 비교는 `==` 대신 `hmac.compare_digest` 사용.

### 5. 인가 (IDOR/BOLA 방어)

- 앱 DB 소유 리소스(k3s 클러스터, union 레이어, 라이브러리, 세션 등)는 path param ID로 접근 시
  `resource.project_id == token_info["project_id"]` 소유권 검증을 **필수**로 한다.
- 관리자 전용 엔드포인트는 `dependencies=[Depends(require_admin)]` 를 반드시 선언한다.
- (참고: OpenStack 스코프 연결 `get_os_conn`은 Keystone이 테넌트 격리를 보장하므로 별도 검증 불필요.)

### 6. 시크릿 관리

- 하드코딩 금지. `config.py` 기본값에 실제 시크릿 금지(기본값은 production 부팅 시 거부되도록 유지).
- 로그에 토큰/비밀번호/키 평문 출력 금지. 5xx 응답에 스택트레이스/내부 경로 노출 금지.
- 비밀 값(password, secret, token, key)은 `generate_k8s.py`의 `render_secret()` 경유 → secret.yaml.
  configmap(평문)에 들어가지 않도록 한다.

### 7. 신규 엔드포인트 보안 체크리스트 (커밋 전 자문)

1. 인증 의존성(`get_token_info`/`require_admin`)이 선언되었는가?
2. 앱 DB 리소스라면 `project_id` 소유권을 검증하는가?
3. 입력이 Pydantic 모델에서 검증되는가? (특히 실행 컨텍스트로 흐르는 값)
4. 그 입력이 쉘/cloud-init/SSH까지 도달한다면 `shlex_quote`로 쿼팅되는가?
5. 보안·인젝션 회귀 테스트를 `backend/tests/`에 추가했는가?
   (참조: `tests/test_k3s_nodegroup_security.py`, `tests/test_ephemeral_mount.py`,
   `tests/test_cloudinit.py`의 인젝션 방어 테스트.)

---

## 커밋 규칙

- 브랜치: 반드시 `dev`
- 커밋 메시지: `type: 요약 (한국어 또는 영어)`
  - type: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- 커밋 전 `git status`로 불필요한 파일 포함 여부 확인

## 금지 사항

- `main` 브랜치 직접 커밋
- `git push --force`
- `.env`, 인증 정보, 시크릿 파일 커밋
- 플래닝 없이 대규모 리팩토링 착수
- 테스트 없이 백엔드 엔드포인트 커밋

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
