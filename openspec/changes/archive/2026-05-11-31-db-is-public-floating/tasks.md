## 27. DB 인스턴스 — `is_public` floating IP 자동 할당 (2026-05-11)

### 27.1 동기

`is_public=True` 로 생성해도 인스턴스에 public IP 가 잡히지 않음. 기존 동작은 `set_instance_access` 만 호출 — Trove 의 access 정책(allowed_cidrs)만 설정하고 floating IP 는 자동 할당하지 않음. 사용자는 "public 으로 표시 = 외부 접근 가능" 으로 기대 → floating IP 자동 할당 필요.

### 27.2 설계

- **`is_public` 의미 확장**: Trove access 정책 + afterglow 의 floating IP best-effort 자동 할당. `set_instance_access` 동작은 유지.
- **신규 인스턴스**: BackgroundTask 로 IP 폴링(5초 간격, 최대 10분) → port 매칭 → 라우터의 외부 네트워크 자동 탐색 → FIP 생성/할당.
- **기존 인스턴스**: DbInstanceDetailPanel 에 "+ 공개 IP 할당" 버튼 (FIP 미할당 시 노출). 사용자 conn 으로 동기 실행.
- **외부 네트워크 선택**: `find_external_network_for_subnets` 자동 탐색 (라우터 → external_gateway_info.network_id). 사용자 명시 선택은 미도입.
- **Port 탐색**: `device_id` 매칭은 service tenant 소유라 불안정 → IP fixed_ips 매칭으로 변경. Trove backend port 는 사용자 네트워크에 attach 되어 user conn 에서 조회 가능.

### 27.3 백엔드

- [x] `api/database/instances.py::_attach_fip_to_instance_sync` — IP→port→external network→FIP 동기 헬퍼. 멱등(이미 할당된 port 는 기존 FIP 반환).
- [x] `api/database/instances.py::_run_attach_fip_bg` — admin connection 으로 BUILD 폴링 + 자동 할당 BG task.
- [x] `api/database/instances.py::create_database_instance` — `BackgroundTasks` 파라미터 + `is_public` 시 BG 등록.
- [x] `api/database/instances.py::attach_floating_ip` — `POST /api/database-instances/{id}/floating-ip` 수동 할당 엔드포인트.
- [x] `api/database/instances.py::detach_floating_ip` — `DELETE /api/database-instances/{id}/floating-ip?delete=true` 해제(또는 삭제).
- [x] `tests/test_db_floating_ip.py` — port 매칭 / 멱등 / IP 미할당/port 미발견/외부망 미발견 에러 검증 (5건).

### 27.4 프런트엔드

- [x] `DbInstanceDetailPanel.svelte` — `FloatingIp` interface, `floatingIps` state, `instanceFips` derived (instance.ips ↔ fip.fixed_ip_address 매칭).
- [x] 연결 정보 섹션에 "공개 IP (Floating)" 행 추가:
  - 미할당 시: "+ 공개 IP 할당" 버튼 (instance.ip 대기 중이면 disabled)
  - 할당된 경우: 에메랄드 칩 + "해제" / "삭제" 버튼
- [x] `attachFip()` / `detachFip(deleteFip)` 함수, 에러 인라인 표시.
- [x] `loadAll()` 에 `/api/networks/floating-ips` 병렬 로드 추가.

### 27.5 검증

- [x] 백엔드 1333 → 1338 (+5), lint/format 통과
- [x] 프런트엔드 타입 체크 통과
- 실 환경 검증 필요 (사용자):
  - 신규 `is_public=true` 생성 → 몇 분 내 BG task 가 FIP 자동 할당
  - 기존 4개 인스턴스에 대해 패널에서 "+ 공개 IP 할당" 클릭 → FIP 즉시 할당
  - 라우터 미설정 환경에서는 "외부 네트워크 미연결" 에러 표시

### 27.6 범위 외

- **외부 네트워크 명시 선택** — 다중 외부망 환경에서 사용자가 직접 선택. 현재는 첫 매칭 라우터의 external network 자동 사용.
- **FIP quota pre-check** — quota 초과 시 Neutron 에서 raise. afterglow 가 사전 검증하지 않음.
- **DbCreatePanel 안내문** — "is_public 시 FIP 자동 할당" 인라인 안내. 별도 PR.

---

