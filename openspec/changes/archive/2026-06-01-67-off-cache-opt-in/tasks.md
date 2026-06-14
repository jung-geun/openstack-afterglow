## Milestone 66 — 백엔드 캐시 기본값 OFF 전환 + 프론트엔드 cache opt-in

### 66.1 개요

캐시 기본값을 ON→OFF로 전환하고, `?cache=true` 쿼리로 opt-in 하도록 변경.
terminal mutation 후 캐시를 직접 패치(surgical write-through)해 mutation 직후 read 가속.
프론트엔드는 `api.get` 기본값을 `?cache=true`로 변경해 warm read 속도 유지.

### 66.2 구현 내역

**Phase 1 — 캐시 코어**

- [x] `backend/app/services/cache/__init__.py` — `cached_call(enabled=False)`: 캐시 read/write 건너뜀, metrics `cache.disabled` 증가
- [x] `backend/app/services/cache/__init__.py` — `write_through(key, ttl, value)`: terminal mutation 직후 known-value 직접 set (origin 재조회 없음)
- [x] `backend/app/services/cache/__init__.py` — `patch_list(key, ttl, *, match, update/remove/add)`: 캐시된 list 엔트리 surgical 패치. 캐시 miss→no-op
- [x] `backend/app/api/deps.py` — `CacheMode(enabled, refresh)` dataclass + `cache_mode` 의존성: `?cache=true`→(True,False), `?refresh=true`→(True,True), 기본→(False,False)

**Phase 2 — READ 엔드포인트 마이그레이션 (27파일 / 66핸들러)**

- [x] 패턴 A (`Depends(cache_bypass)` → `Depends(cache_mode)`): `compute/keypairs`, `compute/flavors`, `container/*`, `database/instances`, `k3s/clusters`, `object_storage/containers`, `storage/volume_*`
- [x] 패턴 B (인라인 `refresh: bool = Query(False)` → `Depends(cache_mode)`): `compute/instances`, `network/*`, `identity/admin*`, `common/dashboard`, `storage/volumes` 등
- [x] refresh 미노출 리소스 (`secrets/*`, `k3s/certificates`, `identity/admin_dashboard`) — `cache_mode` 의존성 신규 추가
- [x] 인프라 캐시 항상 ON 유지: `deps.py._cached_validate`, `identity/auth._prewarm_dashboard`, `common/sd_targets`

**Phase 3 — 하이브리드 write-through (surgical 직접 패치)**

- [x] `backend/app/api/compute/keypairs.py` — `create_keypair`: `invalidate(wildcard)` → `patch_list(list_key, add=list_entry)` / `delete_keypair`: → `patch_list(list_key, match=name, remove=True)`
- [x] `backend/app/api/network/security_groups.py` — `create_security_group`: → `patch_list(sg_key, add=result)` / `delete_security_group`: → `patch_list(sg_key, match=id, remove=True)`. 규칙 create/delete는 중첩 구조로 invalidate 유지
- [x] `backend/tests/test_mutation_invalidate_coverage.py` — `has_invalidation_call` 에 `write_through`/`patch_list` 인식 추가

**Phase 4 — 프론트엔드 opt-in**

- [x] `frontend/src/lib/api/client.ts` — `api.get` URL 빌더: 기본→`?cache=true`, `opts.refresh`→`?refresh=true`, URL에 이미 `refresh=true` 포함→무변경 (수동 조립 3개 경로 보존)

**Phase 5 — 테스트**

- [x] `backend/tests/test_cache_opt_in.py` — 22개 단위 테스트: `cached_call(enabled=False)`, `write_through`, `patch_list`, `cache_mode` 의존성 조합 검증

### 66.3 설계 결정

- **read 기본값**: 캐시 OFF (origin 직행). `?cache=true` opt-in. 인프라 캐시(토큰 검증, prewarm)는 항상 ON.
- **write-through 메커니즘**: surgical 직접 패치 — 요청 스코프 동기 실행, origin 재조회 없음, conn 재사용 없음.
- **flip-flop 방지**: `?refresh=true` → `enabled=True, refresh=True`(재조회+재저장) — 다음 `?cache=true` 조회가 stale 복귀 없음.
- **TTL 안전망**: 패치 오류 staleness는 해당 키 TTL(operational_live 30s 등)로 한정.
- **transitional mutation**: BUILD/creating/deleting 전이 상태는 invalidate만 유지 (write-through 금지).

### 66.4 검증 (사용자 직접)

- [ ] `GET /api/instances` (파라미터 없음) → origin 직행, Redis 키 미생성 확인
- [ ] `GET /api/instances?cache=true` → 1회차 miss→store, 2회차 hit 확인
- [ ] `GET /api/instances?refresh=true` → origin 재조회+재저장, 다음 `?cache=true`가 fresh 반환 확인
- [ ] 키페어 생성 후 `GET /api/keypairs?cache=true` → 새 키페어 즉시 반영 (list 패치)
- [ ] 보안그룹 삭제 후 `GET /api/security-groups?cache=true` → 삭제된 SG 즉시 제거 (list 패치)
- [ ] 프론트 네트워크 탭: 일반 GET → `?cache=true`, 수동 새로고침 → `?refresh=true` 확인

