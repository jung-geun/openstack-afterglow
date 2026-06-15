## Phase 59 — 영구 Builder VM 코드 경로 삭제 (Phase 2) (2026-05-24)

### 59.1 삭제 범위

**`backend/app/services/builder_vm.py`** (−230줄):
- `_BUILDER_VM_NAME`, `_BUILDER_KEYPAIR_NAME`, `_BOOTSTRAP_CLOUD_INIT` 상수 삭제
- `BuilderEndpoint` dataclass, `_cached_endpoint`, `invalidate_cache()` 삭제
- `ensure_builder_vm()`, `_find_existing_server()`, `_create_new_builder_vm()` 삭제
- `_ensure_keypair()` (영구 VM 전용), `_extract_fip()`, `_ensure_fip()` 삭제
- 공유 헬퍼(`_wait_for_active`, `_wait_for_ssh`, `_wait_for_cloud_init`) 및 Ephemeral 경로 전체 유지

**`backend/app/services/library_builder.py`** (−415줄):
- `_update_build_db()`, `_UV_BOOTSTRAP`, `_INSTALL_SCRIPTS`, `_PROGRESS_RE` 삭제
- `_get_lib_size()`, `_build_ssh_command()` 삭제
- `start_build()` (영구 VM SSH 경로) 삭제
- `_ssh_build_task()` 삭제
- `get_active_builds()`, `cancel_build()`, `start_ephemeral_build()`, `_ephemeral_build_task()`, `queue_build()`, `get_build_queue_status()`, `_build_worker()` 유지

**`backend/app/services/ssh_executor.py`** (−48줄):
- `stream_command()` 삭제 (호출처 `_ssh_build_task` 제거됨)
- `run_command()` 유지 (ephemeral VM SSH 헬퍼에서 사용)

**`backend/app/main.py`** (−15줄):
- `_ensure_builder_vm_background()` 함수 및 `create_task` 호출 삭제

**`backend/app/config.py`** (−5줄):
- `builder_persistent_server_id`, `builder_ssh_host` 필드 및 `_load_toml()` 매핑 삭제

**테스트** (−547줄):
- `tests/test_builder_vm.py` 전체 삭제 (모든 테스트가 삭제된 심볼 참조)
- `tests/test_library_builder.py` — 구 SSH 경로 테스트 전부 삭제, queue/worker 테스트 유지
- `tests/test_ssh_executor.py` — `stream_command` 테스트 삭제, `run_command` 테스트 유지

### 59.2 검증

```bash
uv run pytest tests/test_library_builder.py tests/test_ssh_executor.py tests/test_ephemeral_builder_vm.py -v
# 19 passed, 5 warnings
uv run ruff check app/services/library_builder.py app/services/builder_vm.py app/services/ssh_executor.py app/config.py
# All checks passed
```

---

