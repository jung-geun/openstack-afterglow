## 28. k3s 클러스터 생성 asyncio loop 충돌 + 라우트 매칭 순서 + DB 백업 글로벌 목록 (2026-05-11)

### 28.1 동기

- **k3s 클러스터 생성 시 "Future attached to a different loop" 에러**: `keystone.ensure_cluster_manager_user` 가 sync 함수인데 내부에서 `asyncio.run(_db_get())` 으로 SQLAlchemy async session 호출. caller(`clusters.py:374`)는 `await asyncio.to_thread(...)` 로 thread 에서 실행 → thread 의 새 loop 가 SQLAlchemy connection pool 의 원래 loop affinity 와 충돌.
- **`/api/instances/availability-zones` 404**: `instances.py:110` `@router.get("/{instance_id}")` 가 먼저 등록되어 `availability-zones` 를 instance_id 로 해석. FastAPI 는 등록 순서 매칭.
- **`/api/database-instances/backups` 404**: 글로벌 백업 목록 GET 엔드포인트 부재 (DELETE 만 존재). DbCreatePanel 의 백업 복원 폼이 호출.

### 28.2 백엔드 — asyncio loop 충돌 해결

`asyncio.run` 패턴을 제거하고 caller chain 을 async 로 통일.

- [x] `services/keystone.py::ensure_cluster_manager_user` — `async def` 변환. DB 호출은 `await get_manager_credentials(...)` / `await save_manager_credentials(...)` 직접 호출. sync openstacksdk 호출은 `asyncio.to_thread` 로 wrap.
- [x] `services/keystone.py::create_app_credential_for_cluster` — `async def` 변환. `await ensure_...` + `asyncio.to_thread(_create_app_cred_sync, ...)`.
- [x] `services/keystone.py::delete_app_credential` — `async def` 변환 (best-effort). `await ensure_...` + `asyncio.to_thread(_delete_app_cred_sync, ...)`.
- [x] `services/keystone.py::_connect_as_manager` — 헬퍼 추출 (관리 사용자로 openstack.connect, code 중복 제거).
- [x] `services/keystone.py::_ensure_cluster_manager_user_sync_with_admin_conn` / `_create_app_cred_sync` / `_delete_app_cred_sync` — sync 부분 추출 → `asyncio.to_thread` 호출 가능.
- [x] `api/k3s/clusters.py:374, 556, 802` — `await asyncio.to_thread(_keystone.X, ...)` → `await _keystone.X(...)`.

### 28.3 백엔드 — 라우트 충돌 + 글로벌 백업 목록

- [x] `api/compute/instances.py` — `@router.get("/availability-zones")` 를 `/{instance_id}` 위로 이동 (line 92 다음). 기존 line 1804 정의 제거.
- [x] `api/database/instances.py::list_all_backups` — `@router.get("/backups")` 신규. `trove.list_backups(conn)` 호출 (instance_id 없이 전체). project-scoped conn 이라 별도 owner check 불필요.

### 28.4 테스트 업데이트

- [x] `tests/test_keystone_appcred.py` — sync 호출(`uid, pw = ensure_cluster_manager_user(...)`) → `asyncio.run(...)` wrap (4건).
- [x] 기존 1335 → 1338 통과 유지 (회귀 없음).

### 28.5 검증

- [x] 백엔드 1338 테스트 통과, lint/format 통과
- 실 환경 검증 필요:
  - k3s 클러스터 생성 → "different loop" 에러 없이 BUILD 진행
  - `/api/instances/availability-zones` GET 200 응답 (가용 영역 목록)
  - `/api/database-instances/backups` GET 200 응답 (DB 복원 폼에 백업 목록 노출)

### 28.6 범위 외

- **다른 sync keystone 헬퍼의 async 변환** — 동일 호출 패턴이 없는 sync 함수는 그대로 유지 (advisor 권고대로 fix 범위 제한).
- **다른 라우터의 정적-경로 vs `/{id}` 충돌 일괄 검증** — 본 PR 은 보고된 한 건만 수정.

### 28.7 후속: `project_manager_credentials` 테이블 누락 DDL 추가

asyncio loop fix 후 SQL 이 실제 실행되자 다음 에러가 노출됨:
```
pymysql.err.ProgrammingError: (1146, "Table 'afterglow.project_manager_credentials' doesn't exist")
```

`k3s_db.py::get_manager_credentials` / `save_manager_credentials` 가 raw SQL 로 read/write 하는데 ORM 모델 / DDL 누락. (k3s_db.py 의 raw SQL 참조는 이 테이블 1개뿐.)

- [x] `app/database.py::create_tables` — `project_manager_credentials` DDL 추가:
  ```sql
  CREATE TABLE IF NOT EXISTS project_manager_credentials (
    project_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    username VARCHAR(255) NOT NULL,
    encrypted_password TEXT NOT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY ix_project_manager_credentials_user_id (user_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  ```
- [x] 검증: `database_auto_create_tables=True` (기본값) → 백엔드 startup 시 `_deferred_create_tables` 가 자동 실행하여 누락 테이블 생성.
- 사용자 검증: 백엔드 컨테이너 재시작 1회 → k3s 클러스터 재시도 → 정상 진행.

---

