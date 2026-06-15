## 11.5 테스트 인프라 강화 — Phase D (실 OpenStack 통합 테스트 활성화)

- [x] `backend/tests/integration/credentials.py` — `project_b_credentials()` 함수 추가
- [x] `backend/tests/integration/conftest.py` — `project_b_credentials_fx`, `project_b_auth_data`, `project_b_client` 픽스처 추가
- [x] `backend/tests/integration/test_isolation.py` — pytest.skip 제거, 3건 본문 구현 (dynamic 격리, public 노출, 직접 GET 404)
- [x] `backend/tests/integration/test_concurrent_boot.py` — pytest.skip 제거, env var `AFTERGLOW_TEST_CONCURRENT_VMS` 지원, timeout 15분
- [x] `backend/tests/integration/test_resize_overlay.py` — pytest.skip 제거
- [x] `.github/workflows/test.yml` — `test-backend-integration` 잡에 project_b secrets 추가, `-m slow` 마커 적용


