## 11.5 테스트 인프라 강화 — Phase C (MariaDB 실 SQL 통합)

- [x] `docker-compose.yml` — `profiles: ["test"]` MariaDB 11.4 서비스 추가
- [x] `backend/tests/fixtures/__init__.py` — 신규 (fixtures 패키지)
- [x] `backend/tests/test_union_layers_db.py` — 20케이스: INSERT/CTE/FK/격리/mount 실 SQL 검증 (`@pytest.mark.db`)
- [x] `.github/workflows/test.yml` — `test-backend-db` 잡 신규 (dev 브랜치 push 전용, MariaDB 11.4 서비스)

