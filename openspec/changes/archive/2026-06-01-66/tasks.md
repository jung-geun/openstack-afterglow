## 65. 오브젝트 스토리지 휴지통 / 버킷 복구 기능

### 65.1 목표

버킷 내 파일 삭제 및 버킷 자체 삭제 시 일정 기간(기본 30일) 복구 가능하도록 소프트 삭제·휴지통 기능 추가.

### 65.2 구현

**Backend**

- [x] `backend/app/services/bucket_naming.py` — `-trash` 예약 접미사 추가 (사용자 직접 생성 차단)
- [x] `backend/app/services/swift.py` — `list_containers` `include_trash` 파라미터 추가, `copy_object` `extra_headers` 파라미터 추가
- [x] `backend/app/services/swift.py` — 신규 함수: `soft_delete_object`, `bulk_soft_delete_objects`, `list_trash_objects`, `restore_trash_object`, `purge_trash_object`, `purge_expired_trash_objects`
- [x] `backend/app/services/swift.py` — 버킷 소프트 삭제 함수: `soft_delete_container_metadata`, `restore_container_metadata`, `get_container_deleted_at`
- [x] `backend/app/api/object_storage/containers.py` — Redis sorted-set 기반 소프트 삭제 추적 헬퍼 (`_mark_container_deleted`, `_unmark_container_deleted`, `_get_deleted_containers`, `_is_container_deleted`)
- [x] `backend/app/api/object_storage/containers.py` — `DELETE /{c}/objects/{name}` 소프트 삭제 기본 (`?permanent=true` 하드 삭제)
- [x] `backend/app/api/object_storage/containers.py` — `DELETE /{c}` 소프트 삭제 기본 (`?permanent=true` 하드 삭제)
- [x] `backend/app/api/object_storage/containers.py` — `POST ""` 생성 시 소프트 삭제 대기 중 동명 버킷 409 차단
- [x] `backend/app/api/object_storage/containers.py` — 신규 엔드포인트: `GET /{c}/trash`, `POST /{c}/trash/restore`, `DELETE /{c}/trash/{key}`, `GET /trash/containers`, `POST /trash/containers/{name}/restore`, `DELETE /trash/containers/{name}`
- [x] `backend/app/main.py` — `_trash_cleanup_loop` 추가 (1시간 간격, `service_swift_enabled` 게이트, 만료 오브젝트·버킷 영구 삭제)
- [x] `backend/app/main.py` — C-1: `_trash_cleanup_loop`에 Swift 메타→Redis reconcile 패스 추가 (Redis 유실 시 ≤1h 내 소프트 삭제 버킷 자동 재동기화)
- [x] `backend/app/main.py` — C-2: 빈 `{name}-trash` 버킷 자동 정리 (count==0 즉시 삭제 + purge 후 전부 삭제 시 삭제)
- [x] `backend/app/api/object_storage/containers.py` — docstring 오타 수정 (409 반환을 400으로 잘못 기재)
- [x] `backend/app/config.py` — `os_trash_retention_days: int = 30` 필드 추가
- [x] `config.toml.example` — `trash_retention_days = 30` 예시 추가
- [x] `generate_k8s.py` — configmap에 `trash_retention_days` 포함

**Frontend**

- [x] `frontend/src/lib/types/common.ts` — `SwiftContainer`에 `is_trash?`, `is_deleted?`, `deleted_at?` 필드 추가
- [x] `frontend/src/lib/utils/bucketName.ts` — `-trash` 예약 접미사 추가
- [x] `frontend/src/lib/components/object-storage/buckets/BucketRow.svelte` — `휴지통`·`복구 대기` 배지 추가
- [x] `frontend/src/lib/components/object-storage/buckets/TrashNotice.svelte` — 신규 휴지통 안내 컴포넌트
- [x] `frontend/src/routes/dashboard/object-storage/buckets/+page.svelte` — 삭제 확인 문구 변경, 복구 대기 버킷 섹션 추가 (복구/영구 삭제 버튼)
- [x] `frontend/src/routes/admin/object-storage/+page.svelte` — include_trash/include_deleted 포함 쿼리, TrashNotice 조건부 렌더
- [x] `frontend/src/lib/stores/objectBrowser.svelte.ts` — 삭제 확인 문구 "휴지통으로 이동" 톤으로 변경

**Tests**

- [x] `backend/tests/test_bucket_naming.py` — `-trash` 접미사 거부 케이스 추가
- [x] `backend/tests/test_object_storage_trash.py` — 신규: 서비스 단위 + 엔드포인트 통합 테스트 24개 + reconcile·빈버킷정리 검증 6개 (총 30개)

### 65.3 설계 결정

- **객체 휴지통**: 버킷별 `{name}-trash` 숨겨진 버킷 (격리용 `-quarantine` 패턴 미러링). trash 키 형식 `{epoch}/{uuid8}/{original_name}` — purge 루프가 HEAD 없이 이름만으로 만료 판정.
- **버킷 복구**: 제자리 소프트 삭제 (데이터 이동 없음) — Redis sorted-set으로 빠른 필터링 + Swift `X-Container-Meta-Afterglow-Deleted-At` 감사 trail.
- **하드 삭제 경로**: 저수준 `swift.delete_*`는 하드 삭제 유지 — 시스템 경로(quarantine, `_segments`, purge 루프) footgun 차단. HTTP DELETE 핸들러 레벨에서만 소프트 삭제 적용.
- **보관 기간**: 기본 30일, `os_trash_retention_days` config 키로 조정.

### 65.4 검증 (사용자 직접)

- [ ] 파일 삭제 → `{bucket}-trash`에 이동 확인 → 복구 → 원위치
- [ ] 버킷 삭제 → "삭제 대기" 섹션 등장 → 복구 → 버킷 목록 복귀
- [ ] 동명 버킷 재생성 시도 → 409 오류 확인
- [ ] 보관 기간 경과 또는 cleanup loop 실행 → 영구 삭제
- [ ] RGW에서 컨테이너 간 `X-Copy-From` + `X-Object-Meta-*` 동시 설정 지원 확인

---

