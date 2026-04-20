# Afterglow — Claude Code 개발 규정

## 브랜치 전략

| 브랜치 | 용도 | 관리자 |
|--------|------|--------|
| `main` | 프로덕션. 배포 기준 버전 | pie_root (수동 PR/머지) |
| `dev`  | 개발. 모든 AI 개발 작업 대상 | Katherine (AI 에이전트) |

> **규칙**: 반드시 `dev` 브랜치에서만 작업한다. `main` 브랜치에 직접 커밋하지 않는다.
> PR과 `dev → main` 머지는 pie_root가 수행한다.

---

## 개발 워크플로우 (하네스 운용 규정)

Claude Code는 하네스(비인터랙티브 모드)로 실행되므로 **plan 모드를 사용할 수 없다.**
따라서 **모든 개발은 반드시 아래 단계를 순서대로 따른다.**

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
backend/          FastAPI + openstacksdk (Python 3.12+)
  app/api/        OpenStack 서비스별 라우터
  app/services/   OpenStack 클라이언트 래퍼
  app/models/     Pydantic 모델
  app/templates/  cloud-init Jinja2 템플릿

frontend/         SvelteKit + TypeScript + Tailwind CSS 4
  src/routes/     페이지 라우터
  src/lib/        컴포넌트, API 클라이언트, Svelte stores
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI 0.125, Python 3.12, openstacksdk 3.3 |
| Frontend | SvelteKit 2.50, Svelte 5, Tailwind CSS 4 |
| DB/Cache | SQLAlchemy 2.0 (asyncio) + asyncmy, Redis 7 |
| 특화 기능 | k3s 프로비저닝, OverlayFS+Manila, AES-256-GCM kubeconfig |

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
