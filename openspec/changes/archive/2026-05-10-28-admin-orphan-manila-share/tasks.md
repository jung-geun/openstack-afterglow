## 24. Admin Orphan 검출 확장 — Manila share + Security group (2026-05-10)

### 24.1 동기

§23(FIP/Volume)에서 의도적으로 분리해 두었던 두 종류를 같은 엔드포인트에 통합. 둘 다 단일 SDK 응답으로 분별 불가:

- **Manila share**: project가 Keystone에서 사라진 share를 cleanup. project_id 매칭 + Keystone admin 조회 필요.
- **Security group**: afterglow가 자동 생성한 SG(`node_exporter`, `dcgm_exporter`, `union-egress-default`) 중 미부착건 cleanup. 일반명이라 사용자 SG와 충돌 위험 → **description marker 도입으로 분별책 확보**.

### 24.2 SG description marker 도입 (선결)

- [x] `app/services/neutron.py` 상단에 `AFTERGLOW_MANAGED_TAG = "[afterglow-managed]"` 모듈 상수 추가
- [x] 3개 ensure 함수의 description 끝에 ` {tag}` 접미어 부여 — `ensure_union_egress_sg`, `ensure_node_exporter_sg`, `ensure_dcgm_exporter_sg`
- [x] 신규 생성 SG부터 marker 부여. 기존 SG는 idempotent 경로가 description 갱신을 안 하므로 자동 제외(안전 우선). backfill은 별도 PR.

### 24.3 API 확장

- [x] `OrphanCleanupRequest.kind` Literal 확장: `"floating_ip" | "volume" | "manila_share" | "security_group"`
- [x] `OrphanScanResponse`에 `manila_shares`, `security_groups` 필드 추가
- [x] `OrphanShareInfo` (size_gb, project_id, status, snapshot_count 등), `OrphanSecurityGroupInfo` (description, project_id 등) 신규 모델
- [x] `cleanup_orphans` 엔드포인트에 `elif req.kind == "manila_share" / "security_group"` 분기 추가
- [x] 각 ID별 audit log (기존 `rec` 패턴 재사용)

### 24.4 Manila share 안전 가드

- [x] 검출: `manila.list_file_storages(conn, all_tenants=True)` × `keystone.list_all_project_ids()` 차집합. `is_public=True` 제외.
- [x] cleanup 직전 재검증:
  1. `get_file_storage` 재조회 (없으면 이미 삭제)
  2. `keystone.list_all_project_ids()` 재조회 후 project가 복구되었는지 확인 → 복구되면 fail
  3. `list_share_snapshots` 0건 확인 → snapshot 있으면 fail (사용자 데이터 보존 우선)
  4. `status in {available, error}` → 그 외 status는 fail
- [x] `keystone.list_all_project_ids()` 헬퍼 신규 추가 (`app/services/keystone.py`)

### 24.5 Security group 안전 가드

- [x] 검출: `conn.network.security_groups()` 중 `description.endswith(AFTERGLOW_MANAGED_TAG)` + `conn.network.ports()` bulk-fetch 후 attach 0건
- [x] cleanup 직전 재검증:
  1. 모든 port 한 번 fetch → `attached_sg_ids` 셋 빌드 (SDK list-query 가정 회피)
  2. SG 재조회 → marker 재확인 (없으면 fail — 사용자 SG 가능성)
  3. attached 셋 포함 여부 → 포함되면 fail (race)
  4. 통과 시 `neutron.delete_security_group`

### 24.6 정책 사유 (운영자 참고)

- **`is_public=True` Manila share 제외** — project 삭제와 무관하게 운영자/타 프로젝트가 의도적으로 공유한 자원이므로 cleanup 후보 아님.
- **SG description marker 미부여 = 사용자 SG로 간주** — afterglow가 만든 SG만 marker가 있으므로, marker 부재 SG는 자동으로 안전.
- **min_age_days 미적용 (Manila/SG)** — Manila는 project 부재, SG는 marker+attach=0이라는 binary 조건이므로 age 필터가 의미 흐림.

### 24.7 단위 테스트 — `test_admin_orphans.py` +10건

- [x] Manila: invalid project_id 추출 (`all_tenants=True` 호출 검증), is_public 제외 (2건)
- [x] Manila cleanup: project 복구 차단, snapshot 차단, 정상 (3건)
- [x] SG find: marker 요건 (None / "" / suffix 미일치 모두 제외) (1건), attach 1건 이상 제외 (1건)
- [x] SG cleanup: race attach 차단, marker 사라짐 차단, 정상 (3건)

### 24.8 프론트엔드

- [x] `/admin/orphans` 페이지에 두 섹션(Manila, SG) 추가 — 컬럼 / 체크박스 / select-all / 일괄 정리 버튼 패턴 그대로 차용
- [x] 정리 확인 모달에 종류별 안내문 (Manila: project 복구/snapshot 재검증, SG: port re-fetch + marker 재확인)
- [x] SG 섹션 상단에 marker 정책 인라인 안내

### 24.9 검증

- [x] 백엔드 단위 1297 → 1307 (+10), ruff/format 통과
- [x] 프론트엔드 빌드 통과
- 실 환경 검증 (사용자 1회): GET 4종 후보 노출 / 사용자 SG가 후보에 없음 / 1개 cleanup → race-safe 응답

### 24.10 범위 외

- **기존 SG description backfill** — 운영 환경의 기존 SG에 marker 일괄 부여하는 마이그레이션. 별도 PR.
- **Manila metadata 기반 검출** (`union_project_id` 메타 무효 사례) — 본 plan은 OpenStack `share.project_id` 매칭이 1차.
- **사용자가 description에 marker를 박는 행위** — 운영자 책임. UI 안내문에 명시.

---

