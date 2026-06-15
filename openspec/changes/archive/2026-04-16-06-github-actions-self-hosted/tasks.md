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

