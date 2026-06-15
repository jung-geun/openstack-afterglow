## 26. DB 인스턴스 — 사용자 host 지원 / 호스트 정보 표시 / SHUTDOWN 라벨 (2026-05-11)

### 26.1 동기

- DB 사용자 생성이 500 에러 — `conn.database.create_user(instance_id, **user_body)` 가 Trove API 본문(`{"users":[{...}]}`)을 정확히 wrap 하지 못함.
- 사용자 생성 폼이 Trove user identity(`name@host`)의 host 필드를 노출하지 않음 — 동명 다른 host 유저 생성 불가.
- DB 인스턴스 IP 표시가 평탄 리스트라 어떤 네트워크 IP인지 불명확.
- 관리자 페이지에서 삭제 진행 중인 인스턴스가 raw `SHUTDOWN` 상태로만 표시되어 사용자 혼란.

### 26.2 백엔드

- [x] `services/trove.py::create_user` — raw REST(`conn.database.post(/instances/{id}/users)`) 로 교체. `host` 파라미터 추가 (기본 `%`), 페이로드는 `{"users":[{...}]}`.
- [x] `services/trove.py::delete_user` — raw REST(`conn.database.delete(/instances/{id}/users/{name@host})`) 로 교체. host-blind 삭제 방지 (동명 다른 host 유저 구분).
- [x] `services/trove.py::list_users` — 응답 dict 에 `host` 필드 포함 (`getattr(u, "host", "%")`).
- [x] `services/trove.py::_instance_to_dict` — `address_map: dict[str, list[str]]` 추가. Trove `i.addresses` dict → `{"private": ["192.168.0.10"]}` 매핑.
- [x] `models/database.py::CreateUserRequest` — `host: str = "%"` 필드 추가.
- [x] `api/database/instances.py::create_instance_user` — `req.host` 전달 + 실패 시 exception 로그.
- [x] `api/database/instances.py::delete_instance_user` — `host` query param 추가, `trove.delete_user` 에 전달.
- [x] `tests/test_db_users.py` — raw REST payload / host 기본값 / databases 형식 / delete URL host 인코딩 / list_users host / address_map 빌드/빈/우선순위 검증 (12건).

### 26.3 프런트엔드

- [x] `lib/config/statusColors.ts` — `StatusStyle.label?: string`, `SHUTDOWN: { tone: 'neutral', pulse: true, label: '삭제 중' }`.
- [x] `lib/components/ui/StatusChip.svelte` — `s.label ?? status` 로 라벨 우선 사용.
- [x] `lib/components/database/DbInstanceDetailPanel.svelte`:
  - `address_map` 우선, `ips` fallback 으로 "private: 192.168.0.163" 표시 (인스턴스 정보 / 연결 정보 두 영역).
  - 플레이버 ID → `cpu.4c_8g (4vCPU / 8192MB)` 매핑 (`/api/database-instances/flavors` 1회 fetch + 클라이언트 매핑).
  - 사용자 생성 폼: `host` 입력 + 인스턴스 DB 체크박스 선택 (databases 빈 경우 안내).
  - 사용자 목록: `name@host` 표시, 삭제 시 `host` 기준 식별.
  - 인스턴스 헤더 status 라벨에 `SHUTDOWN → "삭제 중"` 표시.

### 26.4 검증

- [x] `tests/test_db_users.py` 10건 + 기존 24건 통과 (총 34건)
- [x] `npm run lint:backend` 통과
- 실 환경 검증 필요 (사용자): 동명 다른 host 유저 동시 생성 / Horizon 형식 IP 표시 / SHUTDOWN 회색 펄스 + "삭제 중" 라벨

### 26.5 범위 외

- **Trove `mgmt/instances/{id}` 폴백** — `i.addresses` 가 비어있을 때 admin API 로 강제 조회. 현재는 `ips` fallback 으로 충분.
- **다른 프로젝트 인스턴스 IP 매핑** — Trove 가 사용자 네트워크에 NIC를 연결하지만 인스턴스 자체는 service tenant 소유. 사용자 권한 내 가능한 정보만 표시.
- **사용자 권한 세분화 (READ/WRITE/ADMIN)** — Trove `databases` 권한 부여만 지원.

---

