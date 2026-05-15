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
milestone.md          기능별 구현 현황 추적
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
- 커밋 전 반드시 실행: `npm run test:all` + `npm run lint:backend`
- 테스트 없는 엔드포인트 구현은 미완료로 간주한다.

### milestone.md 갱신 의무

- 기능 구현 완료 시 `milestone.md`의 해당 항목을 `[ ]` → `[x]`로 업데이트한다.
- 신규 기능을 추가할 경우 milestone.md에 항목을 먼저 추가한 후 구현에 착수한다.

### 설정 파일 동기화 의무

**`config.toml` 항목 추가·변경 시 반드시 함께 갱신:**
- `backend/app/config.py` — `_load_toml()` flat dict + `Settings` 클래스 필드
- `generate_k8s.py` — 비밀 값은 `render_secret()`, 일반 값은 `_render_toml_for_k8s()`
- `config.toml.example` — 새 항목을 예시/주석과 함께 문서화

**`backend/app/config.py` 필드 추가·변경 시 반드시 함께 갱신:**
- `generate_k8s.py` — K8s 배포 시 configmap 또는 secret에 포함되도록
- `config.toml.example` — 해당 TOML 키가 예시 파일에 존재하도록

> 비밀 값(password, secret, token, key) 기준: `render_secret()` → secret.yaml 환경변수로 주입.
> 나머지는 `_render_toml_for_k8s()` → configmap의 config.toml 인라인에 포함.

### Union Mount 설계

- Union Mount 레이어 시스템 구현 시 **`union.md` 를 반드시 먼저 읽는다.**
- Content-addressable 레이어, single-parent 상속, 3-lock 불변성 등 설계 원칙을 따른다.

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

---

## Grafana JWT 시크릿 운영

### 동작 원리

afterglow는 GitLab OIDC로 로그인한 사용자를 위해 **HS256 공유 시크릿**으로 JWT를 서명해
Grafana iframe에 `?auth_token=<jwt>` 쿼리로 전달한다. Grafana는 같은 시크릿으로 검증 후
자동 로그인한다. GitLab/Grafana가 발급하는 토큰이 아니며, 양쪽에 동일한 값만 넣으면 된다.

### 시크릿 주입 위치 (2곳, 반드시 동일)

| 시스템 | 파일 | 환경변수 |
|--------|------|----------|
| afterglow backend | `deploy/k8s/secret.yaml` → `GRAFANA_JWT_SECRET` | `Settings.grafana_jwt_secret` |
| Grafana | `deploy/k8s/grafana-deployment.yaml` → `GF_AUTH_JWT_KEY` | Secret ref 참조 |

`generate_k8s.py`를 실행하면 `config.toml`의 `[monitoring].grafana_jwt_secret` 값을
위 두 곳에 자동으로 동기화한다.

### 시크릿 생성

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 시크릿 회전 절차

1. 새 시크릿 생성 (위 명령)
2. `config.toml`의 `[monitoring].grafana_jwt_secret` 갱신
3. `python3 generate_k8s.py` 재실행 → `secret.yaml` + `grafana-deployment.yaml` 동시 갱신
4. `kubectl apply -f deploy/k8s/secret.yaml -f deploy/k8s/grafana-deployment.yaml`
5. `kubectl rollout restart -n afterglow deploy/backend deploy/grafana`
6. 활성 사용자는 JWT 80% TTL 도달 시 자동 재발급됨 (수동 재로그인 불필요)
