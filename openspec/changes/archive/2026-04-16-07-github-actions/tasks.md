## 7. 버전 관리 통합 + GitHub Actions 수정

> **목표**: 루트 `package.json` 을 단일 버전 진실 소스로 만들고, CI 에서 불일치 시 빌드 차단, PR 은 이미지 미푸시

- [x] 7.1 버전 초기 동기화 (1.13.0 → 1.13.2)
  - [x] `backend/pyproject.toml` — `1.13.0` → `1.13.2`
  - [x] `frontend/package.json` — `1.13.0` → `1.13.2`
  - [x] `backend/uv.lock` — `uv lock` 재생성으로 1.13.2 반영

- [x] 7.2 Node 기반 버전 동기화 스크립트
  - [x] `scripts/sync-version.js` — 루트 package.json → frontend/backend/uv.lock 전파
  - [x] `scripts/check-version-sync.js` — CI 용 일치 검증 (tag push 시 git ref 비교)
  - [x] `package.json` — `version`, `version:sync`, `version:check`, `version:bump:patch/minor/major` 스크립트 추가
  - [x] npm `version` 훅으로 `npm version patch/minor/major` 한 번에 모든 파일 동기화

- [x] 7.3 백엔드 `_read_app_version` 중복 제거
  - [x] `backend/app/utils/version.py` — `read_app_version()` 공용 유틸 신규 생성
  - [x] `backend/app/main.py` — 로컬 `_read_app_version()` 제거, util import 로 치환
  - [x] `backend/app/api/identity/admin.py` — 로컬 `_read_backend_version()` 제거, util import 로 치환

- [x] 7.4 GitHub Actions 문제 수정
  - [x] `docker-build.yml` — PR 에서 `push: false`, `cache-to` 도 PR skip
  - [x] `docker-build.yml` — manifest job 에 `if: github.event_name != 'pull_request'` 가드 추가
  - [x] `docker-build.yml` — checkout 직후 `check-version-sync.js` 검증 스텝 삽입 (tag push 시 git tag ↔ package.json 일치 확인)
  - [x] `test.yml` — 트리거에 `dev` 브랜치 및 `v*` 태그 추가
  - [x] `test.yml` — `version-check` job 신설, `test-backend`/`test-frontend` 가 `needs: version-check` 로 직렬화

