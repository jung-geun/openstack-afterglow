## 75. ERROR 인스턴스 복구 — 자동 진단 + 관리자 확인 후 원클릭 실행

- [x] `app/services/instance_recovery.py` — `analyze_error_instance` (안전 검사 5종 + 시나리오 판정) + `execute_recovery` (fail-closed 재검증 후 순차 실행)
- [x] `app/services/nova.py` — `reset_server_state(conn, server_id, state)` 신규
- [x] `app/services/cinder.py` — `reset_volume_status`에 `attach_status` 파라미터 추가
- [x] `GET /api/admin/instances/{id}/recovery-analysis`, `POST /api/admin/instances/{id}/recover` (관리자 전용, 활동 기록)
- [x] `tests/test_admin_instance_recovery.py` — 시나리오 판정·안전 게이트·실행 순서·409 fail-closed·권한
- [x] `RecoveryModal.svelte` — 진단 체크리스트 + 권장 단계 + 관리자 확인 체크박스 + 실행 결과
- [x] `AdminInstanceTable.svelte` — ERROR 행에 "복구" 버튼 추가
- [x] `adminInstance.ts` — 복구 관련 타입 추가

---

