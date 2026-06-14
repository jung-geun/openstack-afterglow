## 14. 오브젝트 스토리지 대용량 다운로드 + 라이트 모드 색상

### 14.1 문제

- 9.5GB 파일 다운로드 시 `AbortError: The user aborted a request` (5분 fetch timeout + 메모리 blob 적재)
- 한글 파일명 다운로드 시 `IT%E1%84...zip`으로 깨지는 문제
- 버킷 선택 액션바·이동/삭제 버튼이 라이트 모드에서 흐릿/저가독

### 14.2 구현

- [x] `backend/app/api/object_storage/containers.py` — `_make_content_disposition()` 헬퍼 추가 (RFC 5987 `filename*=UTF-8''...` 형식)
- [x] `backend/app/api/object_storage/containers.py` — `POST /{container}/objects/{object:path}/download-token` 신규 엔드포인트 (Redis 단발 토큰, TTL 60초, 1회 사용 강제)
- [x] `backend/app/api/object_storage/containers.py` — `download_object` 토큰 쿼리 파라미터 분기 추가 (헤더 인증 경로 유지)
- [x] `backend/app/api/object_storage/containers.py` — `preview_object` Content-Disposition RFC 5987 적용
- [x] `backend/tests/test_object_storage.py` — Content-Disposition 포맷·토큰 발급·만료·불일치·유효 다운로드 테스트 추가
- [x] `frontend/src/routes/dashboard/object-storage/buckets/[name]/+page.svelte` — `downloadObject()` 단발 토큰 발급 후 브라우저 네이티브 다운로더 트리거로 재작성
- [x] `frontend/src/routes/layout.css` — 인디고 액션바·버튼, 레드 삭제 버튼 `:root.light` 오버라이드 추가

### 14.3 검증 (사용자 직접)

- [ ] 9.5 GB 파일 다운로드 → `AbortError` 없이 브라우저 다운로드 패널에서 진행
- [ ] 한글 파일명("한글 2024.zip" 등) 다운로드 → 저장 파일명 정상
- [ ] 토큰 재사용 시도 → 403
- [ ] 라이트 모드 버킷 상세 → 선택 행·액션바·버튼 색상 가독성 확인

