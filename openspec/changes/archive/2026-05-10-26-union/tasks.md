## 22. Union 멀티 상속 실험 도입 (2026-05-10) — 9.3 마지막 [ ] 마감 (백엔드 한정)

> **배경**: union.md §4.2가 멀티 상속을 opt-in 실험 기능으로 정의 — 단일 상속 MVP 안정화 후 도입. 본 작업은 **백엔드 모델 + 서비스 + API**까지 도입하고, 단위/DB 통합 테스트로 다이아몬드/공통 base 검증 정책을 회귀 보호. layerbuild CLI 확장과 envmgr-use lowerdir 멀티 조립은 **별도 작업**.

### 22.1 설계 결정

- **mutually exclusive 모드**: single-parent는 `parent_id = X, parent_ids = NULL`, multi-parent는 `parent_id = NULL, parent_ids = [X, Y, ...]`. mirror 안 함 (advisor 검토 결과 — mirror하면 자식 검색 모호성 발생).
- **분기 조건**: `parent_ids is not None and len >= 2`. 1개짜리는 422 reject.
- **부모 순서는 정체성** (`union.md §4.2-2`): `[A, B]`와 `[B, A]`는 다른 레이어. overwrite 금지에서 JSON 비교.
- **공통 base 검증** (`union.md §4.2-4`): 모든 부모의 root ubuntu_base가 일치해야 함.
- **다이아몬드 dedup** (`union.md §4.2-3`): BFS + Kahn toposort + 선언 순서 결정성. 같은 조상이 여러 경로로 도달해도 한 번만 등장.

### 22.2 DB 스키마 + ORM

- [x] `backend/app/models/db.py` — `UnionLayer.parent_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)` 추가
- [x] `backend/app/database.py::create_tables` — `ALTER TABLE union_layers ADD COLUMN parent_ids JSON DEFAULT NULL` 마이그레이션 추가

### 22.3 Pydantic 모델

- [x] `backend/app/models/union.py::CreateLayerRequest`:
  - `parent_ids: list[str] | None = None` 추가
  - `field_validator`: 모두 sha256 형식 + dedup + 2개 이상
  - `model_validator`: parent_id와 parent_ids 동시 지정 시 422
- [x] `LayerInfo`: `parent_ids: list[str] | None = None` 응답 필드 추가

### 22.4 서비스 레이어

- [x] `backend/app/services/union_layers.py`:
  - `_is_multi_parent(layer) -> bool` 헬퍼 (`parent_ids and len >= 2`)
  - `_validate_common_base(session, parent_ids)` 신규 — 부모 root까지 거슬러 ubuntu_base 일치 검증
  - `create_layer` 분기: parent_ids 검증(봉인, 자기참조, 공통 base, overwrite 금지 — JSON list 비교)
  - `_get_ancestors_multi(session, leaf_id)` 신규 — Python BFS + Kahn toposort + 선언 순서 결정성 (base-first)
  - `get_ancestors`는 leaf의 모드(`_is_multi_parent`)로 single CTE / multi BFS 분기
  - `delete_layer` / `get_dependents`: single 자식(`parent_id == X`) + multi 자식(`JSON_CONTAINS(parent_ids, X)`) OR 검색. multi 자식은 모든 부모 차단.

### 22.5 API

- POST `/api/union/layers`: 기존 시그니처 유지 (CreateLayerRequest 확장만으로 자동 호환)
- GET `/api/union/layers/{id}/ancestors`: 내부 분기로 자동 처리

### 22.6 단위 테스트 — `TestMultiParent` 11건

- [x] create 성공/실패 6건: success, unsealed_rejected, base_mismatch_rejected, single_item_rejected (Pydantic), both_specified_rejected (Pydantic), overwrite_rejected
- [x] ancestors 2건: diamond_dedup (D 한 번만), multi_topo_order (선언 순서)
- [x] delete 1건: blocked_by_multi_parent_child (A/B 두 부모 모두 차단)
- [x] helper 2건: validate_common_base consistent / mismatch
- [x] `_make_layer` 헬퍼에 `parent_ids` 인자 추가 (MagicMock spec 자동 mock 회피)

### 22.7 DB 통합 테스트 — `test_union_layers_db.py` C3-21

- [x] **다이아몬드 토폴로지 실 SQL 검증**: D→{A, B} → C(parent_ids=[A, B]). C의 조상 체인에 D가 한 번만 등장 + base-first 순. multi 자식 차단 검증 (A/B 둘 다 409).
- MariaDB 11.4 (`@pytest.mark.db`) 환경에서 JSON_CONTAINS 실 동작 검증.

### 22.8 검증

- [x] 백엔드 단위 테스트 1285건 그린 (1274 → 1285, +11 신규)
- [x] union_layers 단위 96건 그린 (회귀 없음)
- [x] ruff check + format 통과
- DB 통합 1건은 셀프호스티드 MariaDB 잡 또는 사용자 환경에서 1회 검증

### 22.9 범위 외

- **layerbuild CLI `--parents A,B,C` 확장** — 별도 작업. 본 plan은 backend API만.
- **envmgr-use 멀티 lowerdir 조립** — 사용자 VM 측 변경. `get_ancestors` 응답을 reverse하여 사용하면 자동 호환.
- **충돌 경로 탐지 (silent shadowing 경고)** — union.md §4.2-1. 빌드 시점 부모 디렉토리 비교 필요. 별도 PR.
- **부모 ID 순서를 hash 입력에 포함** — layerbuild의 `_compute_layer_hash`에 부모 metadata 포함. CLI 변경 동반.
- **join table로 마이그레이션** — 멀티 상속 사용량 증가 후 정식 채택 시 별도 PR.

---

