## 23. Admin Orphan Resource Detection API (2026-05-10) — 운영 가시성 신규

### 23.1 동기

- VM 삭제·빌드 정리 best-effort 경로(`instances.py`, `library_builder.py`)에서 단계적 실패 시 **분리된 FIP** 또는 **장기 미사용 volume**이 누적.
- 기존 admin/floating-ips, admin/all-volumes는 전체 목록만 노출 → 운영자가 수동으로 이상 항목을 식별해야 함.
- **본 작업**: 한 화면에서 orphan 후보를 검색 + 안전 일괄 정리하는 admin 전용 API 도입.

### 23.2 API

- [x] `GET /api/admin/orphans?min_age_days=14` → `{floating_ips: [...], volumes: [...]}` 반환
- [x] `POST /api/admin/orphans/cleanup` body `{kind: "floating_ip"|"volume", ids: [...]}` → `{deleted: [...], failed: [{id, error}]}`
- [x] 두 엔드포인트 모두 `require_admin` 의존, admin scope 토큰 + `all_projects=True`로 cross-project 가시성

### 23.3 검출 정책

- [x] **Floating IP**: `port_id IS NULL` → 즉시 orphan (분리된 즉시)
- [x] **Volume**: `status=available` + `attachments=[]` + `age_days >= min_age_days`(기본 14, 범위 [1, 365])
- [x] `min_age_days=0` 미허용 — 갓 detach된 정상 volume 보호

### 23.4 cleanup 안전 가드 (race-safe)

- [x] **Volume**: delete 직전 `cinder.get_volume` 재조회 → `attachments != []` 또는 `status != available`이면 `failed[]`에 추가, delete 호출 안 함.
- [x] **FIP**: 단순 delete + 예외 catch (분리된 FIP 재attach는 운영자 의도 행위로 race 위험 낮음).
- [x] 각 ID별 audit log 기록 (`rec(... action="orphan.cleanup", status="success"|"failed")`)

### 23.5 단위 테스트 — `test_admin_orphans.py` 12건

- [x] `find_orphan_floating_ips` — port_id NULL 필터 + age_days 계산 (2건)
- [x] `find_orphan_volumes` — min_age_days 필터 + attachments 제외 (2건)
- [x] `cleanup_floating_ips` — 정상 + 부분 실패 (2건)
- [x] `cleanup_volumes` — attachments race / status race / 정상 (3건)
- [x] 엔드포인트 — 비관리자 403 / 잘못된 kind 422 / volume cleanup audit log (3건)

### 23.6 검증

- [x] 백엔드 단위 1297건 그린 (1285 → 1297, +12 신규)
- [x] ruff check + format 통과
- 실 환경 검증 (사용자 1회): `GET /api/admin/orphans` → ID 1개 cleanup → 해당 ID 사라짐 / 비관리자 토큰 → 403

### 23.7 범위 외

- **Manila share orphan 검출** — project 삭제 후 잔존 share. 사용자 데이터 잠재 손실 위험으로 별도 PR. → §24에서 마감.
- **Security group orphan 검출** — afterglow 자동 생성 SG attach 0건. 운영자 정책 변경 가능성. 별도 PR. → §24에서 마감 (description marker 도입).
- **프론트엔드 admin/orphans 페이지** — 백엔드 API만 본 PR. UI 별도 PR.
- **Redis 캐싱** — 호출 빈도 분석 후 별도 PR.
- **Cron 자동 cleanup** — 명시적 작업 유지(안전 우선). 알림만 향후 검토.

---

