## 11.5 테스트 인프라 강화 — Phase B (동어반복 정리)

- [x] `backend/tests/test_union_layers.py` — `patch.object(svc, fn)` 후 fn 재호출 동어반복 2건 삭제 (DB 통합으로 이전)
- [x] `backend/tests/test_k3s_callback.py` — `assert_called_once_with(exact, args)` 강화 (failure/success 시나리오 인자 고정)

