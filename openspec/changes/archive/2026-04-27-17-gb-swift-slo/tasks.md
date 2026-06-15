## 13. 오브젝트 스토리지 5GB+ 대용량 업로드 (Swift SLO)

### 13.1 문제

기존 업로드는 5GB 하드 캡으로 인해 대용량 파일(5GB 초과)을 버킷에 올릴 수 없었다:
- Traefik middleware `maxRequestBodyBytes: 5GB`
- 백엔드 `_MAX_UPLOAD_BYTES = 5GB` + 413 응답
- Swift 단일 PUT 프로토콜 한도 5GB

### 13.2 구현

- [x] `backend/app/services/swift.py` — `_SLO_SEGMENT_SIZE = 1 GiB`; `upload_object` 1 GiB 초과 시 수동 SLO: `_LimitedReader`로 1 GiB씩 `proxy.put()` 루프 → `?multipart-manifest=put` manifest PUT (openstacksdk file-like SLO 버그 우회)
- [x] `backend/app/services/swift.py` — `delete_object` SLO `?multipart-manifest=delete` 정리 (quota 누수 방지)
- [x] `backend/app/api/object_storage/containers.py` — streaming PUT endpoint + `HttpException` 에러 디테일 응답 노출
- [x] `backend/app/config.py` — `os_swift_upload_timeout` 기본값 600 → 1800 (30분)
- [x] `deploy/k8s-template/middleware.yaml` — Traefik buffering 제거 → streaming pass-through
- [x] `backend/tests/test_object_storage.py` — 수동 SLO 루프 검증 테스트 업데이트 (3건)
- [x] `frontend/src/lib/stores/uploadQueue.ts` — 백그라운드 업로드 큐 store
- [x] `frontend/src/lib/components/UploadDock.svelte` — 우하단 업로드 진행 도크 위젯
- [x] `frontend/src/lib/components/UploadModal.svelte` — enqueue+즉시 닫기로 단순화 (진행 UI → Dock)
- [x] `frontend/src/routes/+layout.svelte` — UploadDock 글로벌 마운트
- [x] `frontend/src/routes/dashboard/object-storage/buckets/[name]/+page.svelte` — silent 자동새로고침 + keyed each + DnD 업로드
- [x] `frontend/src/routes/admin/object-storage/[name]/+page.svelte` — 동일 패턴 적용

### 13.3 검증 (사용자 직접)

- [ ] Ceph RGW 9.58 GB 파일 업로드 → 200 응답 + `{container}_segments` 에 10개 세그먼트 확인
- [ ] 다운로드 후 md5 일치
- [ ] 자동새로고침 15초 폴링 중 표 깜빡임 없음
- [ ] DnD로 파일 드롭 → Dock에 진행 표시
- [ ] 업로드 중 다른 페이지 이동 → Dock 유지, 완료 후 목록 자동 갱신

