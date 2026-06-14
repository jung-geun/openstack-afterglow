## 76. NFS 파일 스토리지 생성 실패 수정 — DHSS=False share network 무시 + 마법사 단계 스킵

- [x] `backend/app/services/manila.py` — DHSS=False share type이면 share_network_id 무시(경고 로그), error 상태 share 자동 삭제 후 원인 포함 에러
- [x] `frontend/src/lib/stores/fileStorageWizardStore.svelte.ts` — `dhssEnabled` derived 추가, DHSS=False일 때 네트워크 단계 건너뛰고 바로 생성
- [x] `FileStorageWizard.svelte` — DHSS=False일 때 '네트워크' 단계 인디케이터 숨김 (2단계)
- [x] `FileStorageWizardStep1.svelte` — DHSS=False일 때 버튼 라벨 '생성'으로 변경
- [x] `tests/test_file_storage.py` — DHSS=True/False/조회실패/error상태 시나리오 pytest
- [x] `file_storage.py` — NFS/CEPHFS share_type 미지정 시 proto별 fallback (NFS→os_manila_nfs_share_type)
- [x] `file_storage.py` — Manila RuntimeError → HTTPException 409 + 실패 사유 노출
- [x] `fileStorageWizardStore.svelte.ts` — Promise.allSettled 로 types/networks 독립 로드
- [x] `tests/test_file_storage.py` — NFS/CEPHFS fallback + RuntimeError→409 pytest
- [x] `file_storage.py` — create_access_rule metadata 제거 (Manila CephFS NFS가 metadata 거부 → 400 → 마법사 접근 규칙 추가 실패 원인)
- [x] `file_storage.py` — create_access_rule HTTPStatusError 핸들러 추가, 실패 사유 노출
- [x] `manila.py` — create_access_rule 반환값 `access_id`→`id` + `access_type`/`state` 필드 추가 (마법사 step3 `rule.id` keyed each 바인딩 수정)
- [x] `tests/test_file_storage.py` + `tests/test_create_access_rule_metadata.py` — 위 변경 반영 pytest

---

