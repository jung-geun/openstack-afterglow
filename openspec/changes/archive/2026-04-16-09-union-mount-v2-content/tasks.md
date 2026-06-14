## 9. Union Mount 레이어 시스템 v2 (content-addressable)

> 설계 원문: **`union.md`** — 구현 전 반드시 먼저 읽는다.
>
> **핵심 원칙**: content-addressable 불변 레이어 | single-parent 상속(MVP) | Manila 3개 share(RW/RO/manifest) | overlayfs upperdir = 로컬 디스크

### 9.1 Phase 1 — MVP ✅ 코드 완료 (인프라 미설정)

**Manila + CephFS 기반 레이어 스토리지 구성**

- [ ] Manila share 3개 실제 프로비저닝: `layer-store-rw` (Builder RW), `layer-store-ro` (User RO), `manifest-store`
- [ ] Builder VM 설정: LAYER_STORE_RW 마운트, `layerbuild` CLI + 의존성 설치
- [x] `layerbuild` CLI (`scripts/layerbuild.py`):
  - `layerbuild init <name> --version <ver> [--parent <sha256:hash>]` — 작업 디렉토리 생성 + overlay/bind 마운트
  - `layerbuild exec <recipe.sh>` — `systemd-nspawn -D merged/ bash recipe.sh` 격리 실행
  - `layerbuild seal` — 결정적 sha256 계산, `sha256-<hash>/diff/` 이동, 3-lock (chmod+chattr+API seal), API 레이어 등록
  - `layerbuild abort` — 진행 중인 빌드 취소 및 마운트 해제
  - `layerbuild --dry-run <cmd>` — destructive subprocess + API 호출을 트레이스만 출력 (21항)
  - `layerbuild resume-api <sha256:hash>` — seal 시 API 등록 실패한 레이어 재등록 (`.api_pending` 마커, 21항)

**MySQL 8.0 스키마 + Pydantic 모델**

- [x] `backend/app/models/union.py` — Pydantic 모델: `LayerInfo`, `TemplateInfo`, `CreateLayerRequest`, `CreateTemplateRequest`, `AncestorChain`, `SealLayerResponse`
- [x] `backend/app/models/db.py` — ORM: `UnionLayer`, `UnionTemplate`, `UnionUserMount` (SQLAlchemy async)
- [x] `backend/app/database.py` — `CREATE TABLE IF NOT EXISTS union_layers / union_templates / union_user_mounts` DDL (MySQL 8.0+, InnoDB, utf8mb4)
- [x] `backend/app/services/union_layers.py` — 서비스 레이어: CRUD + MySQL `WITH RECURSIVE` CTE 조상 쿼리 + 템플릿 관리

**REST API (Backend)** — `/api/union` 접두어, `backend/app/api/union/`

- [x] `GET /api/union/layers` — 레이어 목록 (페이지네이션, `?name=` 필터)
- [x] `GET /api/union/layers/{id}` — 레이어 상세 조회
- [x] `POST /api/union/layers` — 새 레이어 등록 (sealed=false, 관리자 전용)
- [x] `POST /api/union/layers/{id}/seal` — 레이어 봉인 (관리자 전용, 봉인 후 수정 불가)
- [x] `GET /api/union/layers/{id}/ancestors` — 조상 체인 반환 base-first 순 (lowerdir 조립용)
- [x] `GET /api/union/templates` — 템플릿 목록
- [x] `POST /api/union/templates` — 템플릿 생성 (봉인된 leaf만 허용, 관리자 전용)

**User VM envmgr**

- [x] `scripts/envmgr-init.sh` — cloud-init 통합: CephFS RO share 마운트, envmgr-use 설치, systemd `layer-store-ro.mount` unit 등록
- [x] `scripts/envmgr-use.sh` — 환경 활성화:
  - `envmgr-use <sha256:...>` — leaf 레이어 직접 지정
  - `envmgr-use --template <name>@<ver>` — 템플릿으로 활성화 (API 조회)
  - `envmgr-use --unmount` / `--status`
  - 조상 체인 API 조회 → lowerdir 조립 → upperdir=`/var/overlay/<hash>/upper` (로컬 디스크) → `mount -t overlay /mnt/env`

**테스트**

- [x] `backend/tests/test_union_layers.py` — Layer CRUD(5), Seal(3), ListLayers(2), GetAncestors(3), LayerIdValidation(3), Templates(3), API(11), Dependents(3), DeleteLayer(5), NewAPI(7) = **45개**

### 9.2 Phase 2 — 운영 (목표: Phase 1 완료 후 ~3주)

**Frontend UI**

- [x] `/dashboard/library` 라우트: 레이어 카탈로그 페이지 (트리 시각화)
- [x] `/dashboard/library/create` — 새 레이어 생성 폼 (관리자 전용)
- [x] `/dashboard/library/[id]` — 레이어 상세: 조상 체인, seal 상태, 파생 레이어 목록, seal/삭제 액션
- [x] `/dashboard/library/templates` — 템플릿 관리 UI (목록 + 생성 폼 + 슬라이드 패널 상세)
- [x] VM 생성 wizard — Step 3에 "라이브러리 선택" / "템플릿 선택" 탭 추가 (`SelectTemplate.svelte`)
- [x] Dashboard 사이드바에 "라이브러리" 섹션 추가
- [x] Admin 사이드바에 "라이브러리" 섹션 추가

**보안 + 격리**

- [x] Manila access rule 자동 관리: Builder VM RW 추가/제거 API (`POST /api/union/builder/access`, `DELETE /api/union/builder/access/{id}`)
- [x] 레이어 프로젝트 격리: `project_id` 컬럼 + `list_layers()` 필터링 (NULL=공유, 값=프로젝트 전용, admin=전체)
- [x] seal 후 RW 접근 차단 검증

**운영 도구**

- [x] `GET /api/union/layers/{id}/dependents` — 자식 레이어 목록 (삭제 전 확인용)
- [x] `DELETE /api/union/layers/{id}` — 수동 GC 엔드포인트 (관리자, 자식/템플릿/마운트 참조 있으면 409)
- [x] `GET /api/union/templates/{name}/{version}` — 템플릿 상세 엔드포인트 (resolved_stack 포함)
- [x] 레이어 크기 집계: `GET /api/union/stats/storage` — `size_bytes`/`file_count` SQL SUM 집계 (`total_layers`, `sealed_layers`, `total_size_bytes`, `total_file_count`)
- [x] 마운트 API: `POST /api/union/mounts` (기록), `POST /api/union/mounts/{id}/unmount` (해제), `sealed_at` 봉인 타임스탬프 추가

**테스트 확장**

- [x] Integration test: Builder VM → seal → User VM mount 전체 플로우 — `tests/integration/test_union_e2e.py` (19항). create→seal→fork→template→record_mount→409 가드→unmount→cleanup 13단계 검증
- [x] 삭제 차단 동작 검증 (자식/템플릿/활성 마운트 — 단위 테스트 포함)

### 9.3 Phase 3 — 확장 (목표: Phase 2 완료 후)

- [x] **Fork 지원**: `POST /api/union/layers/{id}/fork` — sealed 레이어에서 새 RW 레이어 파생
- [x] **Rebuild**: 동일 부모 + 다른 내용 → 새 hash 신규 레이어 (overwrite 금지 정책 유지)
- [x] **멀티 상속(실험)**: lowerdir에 여러 부모 지원 — 다이아몬드 충돌 해결 정책 필요. 22항 참조 (백엔드 API + DB + 서비스 레이어 도입, layerbuild CLI/envmgr 확장은 별도 작업)
- [x] **OverlayFS 상태 모니터링 에이전트**: User VM에서 마운트 상태 주기적 보고
- [x] **Manila Share Snapshot 관리**: 레이어 백업/복원

---

