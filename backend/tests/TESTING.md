# 백엔드 테스트 실행 가이드

## 빠른 시작

```bash
cd backend

# 단위 테스트 (외부 의존성 없음, 수초 내 완료)
AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/ --ignore=tests/integration -v

# 통합 테스트 (실제 OpenStack + Redis 필요)
AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/ -v
```

> **주의**: 환경변수는 `AFTERGLOW_ALLOW_INSECURE=1` (코드 기준). CLAUDE.md 문서의 `UNION_ALLOW_INSECURE`는 오기.

---

## 테스트 계층 구조

```
backend/tests/
├── conftest.py                  # 단위 테스트 공통 픽스처 (mock OpenStack)
├── test_*.py                    # 단위 테스트 (mock 기반, 빠름)
├── test_endpoint_inventory.py  # 라우트 카탈로그 회귀 방지
└── integration/
    ├── conftest.py              # 통합 테스트 픽스처 (실제 OpenStack)
    ├── credentials.toml.example # 크리덴셜 템플릿
    ├── credentials.py           # 크리덴셜 로더
    └── test_*.py                # 통합 테스트 (실제 인증)
```

---

## 크리덴셜 설정 (통합 테스트)

### 방법 A: credentials.toml (로컬 개발)

```bash
cp tests/integration/credentials.toml.example tests/integration/credentials.toml
# 파일을 열어 admin 및 user 비밀번호 기입
vim tests/integration/credentials.toml
```

`credentials.toml` 파일은 `.gitignore` 에 포함되어 커밋되지 않는다.

### 방법 B: 환경변수 (CI/CD)

```bash
export AFTERGLOW_TEST_ADMIN_USERNAME=admin
export AFTERGLOW_TEST_ADMIN_PASSWORD=secret
export AFTERGLOW_TEST_ADMIN_PROJECT=admin
export AFTERGLOW_TEST_ADMIN_DOMAIN=Default

export AFTERGLOW_TEST_USER_USERNAME=testuser
export AFTERGLOW_TEST_USER_PASSWORD=secret
export AFTERGLOW_TEST_USER_PROJECT=test-project
export AFTERGLOW_TEST_USER_DOMAIN=Default
```

### 우선순위

환경변수 > `credentials.toml` > `config.toml [openstack]`

admin 계정은 `config.toml [openstack]` 으로 폴백되므로 로컬에서 별도 설정 없이도 admin 테스트는 동작한다.
일반 유저 계정이 없으면 `user_client` 픽스처가 필요한 테스트는 자동으로 **skip** 된다.

---

## 테스트 픽스처

### 단위 테스트 (`tests/conftest.py`)

| 픽스처 | 설명 |
|---|---|
| `client` | member role, `is_system_admin=False` |
| `admin_client` | admin+member role, `is_system_admin=True` |
| `non_admin_client` | member role, `is_system_admin=False` — 403 테스트용 |
| `mock_conn` | MagicMock OpenStack Connection |

### 통합 테스트 (`tests/integration/conftest.py`)

| 픽스처 | 설명 |
|---|---|
| `client` | admin 계정 AsyncClient (기존 호환) |
| `admin_client` | admin 계정 AsyncClient |
| `user_client` | 일반 유저 AsyncClient (미설정 시 skip) |
| `anon_client` | 인증 없는 AsyncClient |
| `admin_auth_data` | admin 로그인 응답 (token, project_id 등) |
| `user_auth_data` | user 로그인 응답 |

---

## 선택적 서비스 테스트

Manila, Magnum, Zun, k3s 는 `config.toml [services]` 에서 활성화되어야 라우터가 등록된다.
비활성화 상태에서 해당 테스트를 실행하면 **skip** 된다.

```bash
# manila 테스트 포함 실행
SERVICE_MANILA_ENABLED=true AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/test_file_storage.py -v
```

---

## 권한 분리 테스트

admin 엔드포인트 77개에 대해 admin 계정(200)과 일반 유저(403)를 쌍으로 검증:

```bash
# 권한 분리 테스트만 실행
AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/test_admin.py -v -k permission

# 단위 테스트에서 require_admin 전체 확인
AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/ --ignore=tests/integration -v -k requires_admin
```

---

## CI/CD 설정

GitLab CI `.gitlab-ci.yml` 참고:

- `test-backend` (자동 실행): 단위 테스트 + Redis service container
- `integration-backend` (manual trigger): 통합 테스트, `AFTERGLOW_TEST_*` CI/CD variables 필요

---

## 일반 유저 계정 준비 (최초 1회)

OpenStack에서 테스트 전용 계정을 생성:

```bash
# admin 프로젝트에 admin role 이 없는 일반 사용자
openstack user create --password <pw> testuser
openstack project create test-project
openstack role add --user testuser --project test-project member
```

이 계정으로 `credentials.toml [user]` 를 채우거나 환경변수로 주입한다.
