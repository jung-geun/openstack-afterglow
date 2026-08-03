---
title: 국소 기능테스트 가이드
lang: ko
nav_order: 8
---

# 국소 기능테스트 가이드

## 원칙

- 개발 루프에서는 먼저 변경한 테스트를 정확한 경로로 실행하고, 다음으로 가장 가까운 named target을 실행한 뒤, 마지막으로 이번 변경이 건드린 교차 관심사 target까지 확인한다.
- 국소 테스트는 개발 중 근거일 뿐이다. 커밋/푸시 전 프로젝트 게이트는 그대로 `npm run test:all` 후 `npm run lint:backend` 이다.
- skip 된 DB 테스트나 통합 테스트는 검증 완료가 아니다. 자격 증명이나 `AFTERGLOW_TEST_DATABASE_URL` 이 없으면 성공으로 주장하지 말고 검증 공백으로 보고한다.

## 빠른 명령

```bash
npm run test:list
npm run test:target -- auth layers
npm run test:target -- --parallel instances
npm run test:target -- backend:tests/test_instances.py::test_delete_instance
npm run test:target -- frontend:src/lib/config/site.test.ts
npm run test:auth -- --dry-run
npm run test:db
```

`test:db`는 Docker Compose의 `test` 프로필로 로컬 MariaDB를 자동 기동한다.
이미 실행 중인 DB를 재사용하려면 `npm run test:db -- --no-start`를 사용한다.
다른 DB를 사용하려면 `AFTERGLOW_TEST_DATABASE_URL`을 지정한다.

## 타깃 선택표

| 타깃 | 언제 실행할까 |
|---|---|
| `auth` | 로그인/로그아웃, 토큰, 세션, site-config 인증 경로를 건드렸을 때 |
| `access` | 관리자 전용 체크, owner check, IDOR/BOLA, audit prefix, legacy v1 계약을 바꿨을 때 |
| `config` | afterglow.conf/config, K8s 설정 생성, 캐시 설정, 프론트엔드 런타임 config를 바꿨을 때 |
| `crypto` | k3s 암호화 또는 키 파생 로직을 바꿨을 때 |
| `db` | 실제 MariaDB 위에서 union layer/license SQL 동작을 확인해야 할 때 |
| `instances` | Nova 인스턴스 API, 메타데이터/메트릭/헬스, 인스턴스 UI를 바꿨을 때 |
| `storage` | Cinder/Manila/Swift 스토리지 API 또는 스토리지 UI를 바꿨을 때 |
| `layers` | admin libraries, squashfs, union layer build/consume 플로우를 바꿨을 때 |
| `k3s` | k3s API, cloud-init, 보안, 플러그인, nodegroup 테스트를 건드렸을 때 |
| `workers` | worker runtime, notion worker 템플릿/동작을 바꿨을 때 |
| `design` | 디자인 시스템 규칙, raw visual debt guardrail을 확인할 때. npm 별칭은 계속 `npm run test:frontend:design` 이다. |
| `integration:*` | 실제 Redis + OpenStack 이 필요한 live 통합 슬라이스를 확인할 때 |

## 백엔드 직접 실행

루트 래퍼로 정확한 pytest selector를 실행할 수 있다.

```bash
npm run test:target -- backend:tests/test_instances.py::test_delete_instance
```

백엔드와 프론트엔드 step이 함께 있는 target(`instances`, `auth`, `config` 등)은 `--parallel` 을 붙이면
backend lane 1개와 frontend lane 1개를 동시에 실행한다. 각 lane 내부 순서는 그대로 유지하므로,
pytest 프로세스끼리 섞지 않고도 국소 확인 시간을 줄일 수 있다.

```bash
npm run test:target -- --parallel instances
```

직접 pytest를 호출하려면 아래와 같다.

```bash
cd backend && AFTERGLOW_ALLOW_INSECURE=1 uv run python -m pytest tests/test_instances.py::test_delete_instance -v
```

## 프론트엔드 직접 실행

루트 래퍼로 Vitest 파일 하나를 직접 실행할 수 있다.

```bash
npm run test:target -- frontend:src/routes/__tests__/logout-flow.test.ts
```

직접 Vitest를 호출하려면 아래와 같다.

```bash
cd frontend && npm test -- src/routes/__tests__/logout-flow.test.ts
```

## DB와 통합 테스트 사전조건

- `db`: `npm run test:db`가 Docker Compose의 `mariadb` test profile을 기동하고 `pytest.mark.db` 전체를 실행한다. 기본 URL은 `mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_pytest` 이며, 직접 target을 실행할 때는 `AFTERGLOW_TEST_DATABASE_URL`이 필요하다. 이 URL은 실행 중인 애플리케이션의 database schema와 달라야 한다.
- `integration:*`: 실제 Redis 와 OpenStack 자격 증명이 필요하다. 입력원은 환경변수, `backend/tests/integration/credentials.toml`, 또는 기존 config fallback 이다. 선택적 user/project-b/SSH 변수 부족으로 일부 테스트가 skip 될 수 있다.

## 에이전트 규칙

- 백엔드 엔드포인트를 수정하면 먼저 `backend/tests` 를 추가/수정하고, 그 정확한 selector를 실행한 뒤 관련 named target을 실행한다.
- 인증/권한/owner check 를 수정하면 직접 변경한 테스트가 통과해도 `auth` 또는 `access` 를 반드시 포함한다.
- config, DB 모델, OpenStack 리소스, 프론트엔드 design token 을 수정하면 직접 변경한 테스트가 통과해도 대응하는 target을 추가로 실행한다.
- 이 가이드는 커밋 게이트를 대체하지 않는다. 커밋 또는 푸시 시에는 여전히 AGENTS.md 순서대로 `npm run test:all` 과 `npm run lint:backend` 를 실행한다.
