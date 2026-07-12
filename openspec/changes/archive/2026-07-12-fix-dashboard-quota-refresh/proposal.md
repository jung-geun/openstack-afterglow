## Why

대시보드의 `GET /api/v1/dashboard/quotas?view=overview`가 반복해서 503을 반환해 Block Volume과 Floating IP 카드가 `갱신 실패`로 남는다. 2026-07-12 운영 로그는 strict Neutron quota validation에서 `floatingip` limit을 찾지 못해 실패한 정확한 stack trace와 5.49초 503을 기록한다.

## What Changes

- Neutron `QuotaDetails`를 strict overview 경로에서 API 원본 key 이름으로 직렬화한다. openstacksdk 기본 `to_dict()`는 `floatingip`를 Python alias `floating_ips`로 바꾸므로 strict validator가 실제 usage-bearing field를 놓친다.
- SDK-shaped `QuotaDetails` regression test로 overview quota가 `floatingip` limit/used를 보존함을 고정한다.
- 기존 strict fail-closed 규칙은 유지한다. 실제 missing/malformed `floatingip` data는 계속 overview 503이어야 한다.

## Impact

- `backend/app/services/neutron.py`
- `backend/tests/test_neutron.py` 및 대시보드 quota regression tests
- Full/default quota wire contract, Manila/Nova/Cinder 동작, frontend request lifecycle은 변경하지 않는다.
