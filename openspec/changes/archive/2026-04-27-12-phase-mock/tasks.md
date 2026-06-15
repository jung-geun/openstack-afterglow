## 11.5 테스트 인프라 강화 — Phase A (mock 트로이 목마 → 실 검증 전환)

- [x] `backend/pyproject.toml` — pytest markers 4개(slow/db/redis/crypto) + `fakeredis[lua]>=2.21` dev 의존성 추가
- [x] `backend/tests/test_k3s_crypto.py` — AES-256-GCM 18케이스 신규 (0% → ≥95% 라인 커버)
- [x] `backend/tests/test_k3s_kube.py` — 4단 nested patch 제거 → `assert_called_once_with(url, headers=...)` URL 검증
- [x] `backend/tests/test_dashboard.py` — `patch("...asyncio")` 제거, `cached_call` side_effect 리스트로 대체, `status_code == 200` 단정
- [x] `backend/tests/test_loadbalancers.py` — 모든 success 케이스에 `assert_called_once_with(...)` 인자 검증 추가
- [x] `backend/tests/test_admin_libraries.py` — `cancel_build` mock `assert_called_once_with(conn, build_id)` 강화
- [x] `backend/tests/test_admin_endpoints.py` — 432줄 트로이 목마 전수 삭제 (`test_endpoint_inventory.py`의 메타 검증과 100% 중복 확인)

