## 70. 라이브러리 기능 저수준 E2E — python 3.11 파일 스토리지 라이프사이클 (2026-06-10)

### 70.1 동기

7단계 인수 시나리오: backend API로 file storage 생성 → 해당 share를 빌더 VM에 연결해 uv로 python 3.11 설치 → cloud-init 완료·prebuilt 승격 → 새 VM에서 overlayfs(/opt/layers/merged)로 python3.11 실제 실행 확인 → teardown. "저수준 단계별 경로"(사용자 생성 share를 빌더에 직접 지정)를 지원하기 위한 최소 신규 코드 + E2E 테스트.

### 70.2 백엔드 코드 변경

- [x] `backend/app/api/identity/admin_libraries.py` — `TriggerBuildRequest`에 `file_storage_id: str | None` 추가. `trigger_library_build`가 `queue_build(existing_share_id=req.file_storage_id)` 전달.
- [x] `backend/app/services/library_builder.py` — `_build_queue` 타입 `Queue[str]` → `Queue[tuple[str, str | None]]`. `queue_build`, `start_ephemeral_build`, `_ephemeral_build_task`, `_build_worker` 모두 `existing_share_id` 파라미터 관통.
- [x] `backend/app/services/ephemeral_build.py` — `run_ephemeral_build`에 `existing_share_id: str | None = None` 추가. 지정 시 `create_builder_share` 건너뛰고 service conn guard(`get_file_storage`) + `update_share_metadata(building)` 후 기존 파이프라인(port·access rule·cloud-init·boot·sentinel·_handle_success·teardown) 재사용.
- [x] `backend/tests/integration/ssh_helper.py` — `verify_python_executes(host, key, version, user)` 추가: 절대경로 `/opt/layers/merged/usr/local/bin/python<version>` 실행 + `command -v` 경로 검증. uv standalone CPython이 cp -a + overlayfs 통과 후 실제 동작하는지 확인.

### 70.3 테스트

- [x] `backend/tests/test_existing_share_build.py` (신규, mock 단위 테스트 3건):
  - existing_share_id 지정 시 `create_builder_share` 미호출, `get_file_storage` guard + `update_share_metadata(building)` 호출 검증
  - guard 실패(share 미발견) 시 `create_builder_share` 미호출, 빌드 error 처리
  - existing_share_id 미지정(기본 경로) 시 `create_builder_share` 정상 호출
- [x] `backend/tests/integration/test_python311_lifecycle_e2e.py` (신규, `pytest.mark.slow` + env-gated):
  - Step 1: `POST /api/file-storage` → share 생성
  - Step 2–5: `POST /api/admin/libraries/build {file_storage_id}` → 빌드 완료 폴링(~30분)
  - Step 6–7: `POST /api/instances {strategy:prebuilt}` → ACTIVE → FIP → SSH → `verify_overlay_mount` + `verify_python_executes`
  - cleanup: `DELETE /api/instances/{id}`

### 70.4 환경 요건 (라이브 E2E)

`AFTERGLOW_TEST_IMAGE_ID`, `AFTERGLOW_TEST_FLAVOR_SMALL`, `AFTERGLOW_TEST_SSH_KEY`, Manila(cephfsnfstype), Nova. MariaDB 비가용 시 DB 비가용 모드(build_id=None)로 share 메타데이터 폴링 fallback 동작.

### 70.5 검증

- [x] `uv run pytest tests/test_existing_share_build.py -v` — 3 passed
- [x] `uv run ruff check .` — All checks passed
- [x] **라이브 E2E step 1–6 통과** (2026-06-10, `AFTERGLOW_SKIP_SSH=1`, 17분 9초):
  - Step 1: `POST /api/file-storage` → Manila share 생성 ✓
  - Step 2: 빌더 VM 부팅 → uv python install → Python ThreadPoolExecutor×16 병렬 복사 (~10분) ✓
  - Step 3: cloud-init SHUTOFF → sentinel 조기 감지(early_success) → prebuilt 승격 + VM/port 자동 teardown ✓
  - Step 6: consumer VM → python311 prebuilt share RO 마운트(union_share_ids 일치) ✓
  - Step 4·7(SSH): **FIP 네트워크 미도달 환경에서 skip** — `AFTERGLOW_SKIP_SSH=1` 제거 후 OpenStack 내부 환경에서 별도 검증 필요
  - 주요 수정 사항: NFS parallel copy 16×, `_SHUTOFF_MAX_WAIT=3600`, early_success fallback, `include_public=True` prebuilt 조회, 최신 prebuilt 우선 선택, consumer VM keypair 지정

### 70.6 sentinel 경쟁 조건 수정 + step 4·7 검증 완료 (2026-06-11)

- [x] **sentinel 감지 경쟁 조건 발견·수정**: 1차 재실행에서 빌드는 성공했으나 sentinel 미감지로 `indeterminate` 판정.
  원인 — 빌더 cloud-init이 sentinel echo 직후(1–2s) poweroff하는데, 오케스트레이터의 ACTIVE 콘솔 폴링은 15s 간격이고
  이 하이퍼바이저는 **SHUTOFF 후 console_output을 반환하지 않음**(빈 응답). 06-10 통과는 우연히 윈도우에 걸린 것.
  수정 — `cloud_init_builder.py:_render_runcmd_body`: sentinel echo 후 `sleep 60` 추가로 조기 감지 윈도우를 결정적으로 확보.
- [x] **라이브 E2E step 1–6 재통과** (2026-06-11, 수정 적용 후): share 생성 → 빌드 8분(sentinel 조기 감지 4회 확인) →
  prebuilt 승격(share `c95fe168`) + teardown → consumer VM이 신규 share 마운트(union_share_ids 일치) ✓
- [x] **step 4·7 검증 완료** (콘솔 sentinel 방식, SSH 불요): Mac VPN이 FIP 대역(172.30.102.x) 라우팅 불가(SG는 tcp/22 open 확인)
  → OpenStack 내부 검증 VM으로 prebuilt share를 RO+noexec 마운트 + overlayfs 구성 + 실행 검증:
  - NFS RO 마운트 `rc=0`, `.union_build_complete` 존재 ✓
  - overlayfs `/opt/layers/merged` 마운트 `rc=0` ✓
  - **`/opt/layers/merged/usr/local/bin/python3.11 --version` → `Python 3.11.15` 실행 성공** ✓ (step 7 동등 검증)
  - noexec lower 직접 실행은 `rc=126 Permission denied` — overlay 경유 실행 설계 확인 ✓
- 미해결: 테스트 step 4·7의 SSH 경로 자체는 FIP 도달 가능 호스트에서 실행해야 통과 가능 (환경 제약, 코드 문제 아님).
  잔여 리소스 — 1차 실패 share `3551a269`(python311-e2e-test, indeterminate, 20GB)는 수동 정리 필요.

---

