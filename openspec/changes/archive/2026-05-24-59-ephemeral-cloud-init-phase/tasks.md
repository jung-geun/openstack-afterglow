## 58. 라이브러리 빌드: Ephemeral cloud-init 자동완결 파이프라인 (Phase 0+1) (2026-05-24)

### 58.1 목표

영구 상주 Builder VM + asyncssh 스트림 방식을 **Ephemeral VM + cloud-init 자율 완결**로 전환 (Phase 0: DB 외부화, Phase 1: 핵심 파이프라인).

### 58.2 구현

**Phase 0 — DB Recipe 외부화**
- [x] `app/models/db.py` — `LibraryRecipe` 모델 추가 (library_id·version·commands·apt_packages·pip_packages·share_proto·share_size_gb·cloud_init_template_version)
- [x] `app/models/db.py` — `LibraryBuild` 에 컬럼 추가: `recipe_id`, `port_id`, `build_token` (CHAR 32, unique idx), `console_log_excerpt`, `cloud_init_status`
- [x] `app/database.py` — `library_builds` ALTER TABLE 마이그레이션 (신규 컬럼 idempotent 추가)
- [x] `app/services/library_recipes.py` (신규) — `get_recipe(library_id)` / `seed_default_recipes()` (python311·torch·vllm·jupyter·pytorch 5개 seed)
- [x] `app/main.py` — 앱 시작 시 `seed_default_recipes()` 호출

**Phase 1 — 핵심 파이프라인**
- [x] `app/services/cloud_init_builder.py` (신규) — `render_user_data(recipe, mount_spec, build_token)` 순수 함수. NFS/CephFS 분기, sentinel `::AFTERGLOW::SUCCESS/FAILURE::<token>`, `tee /dev/console`, `_rc=0; chain || _rc=$?` 패턴, `power_state: {mode: poweroff}`
- [x] `app/services/neutron.py` — `create_port(conn, network_id, name, security_group_ids=None)` 추가
- [x] `app/services/nova.py` — `get_console_output(conn, server_id, length=None)` 추가 (length=None → 전체 조회)
- [x] `app/services/ephemeral_build.py` (신규) — 8단계 오케스트레이터 `run_ephemeral_build(library_id, build_db_id)`: Recipe로드→Share생성→Port사전생성(IP예약)→AccessRule→ExportLocation→VM생성→SHUTOFF폴링(30분)→Sentinel grep→성공/실패/indeterminate 처리, finally: server+port 항상 정리
- [x] `app/services/library_builder.py` — `start_ephemeral_build(library_id)` 및 `_ephemeral_build_task()` 추가, `_build_worker()` → `start_ephemeral_build` 호출로 전환

**테스트**
- [x] `tests/test_cloud_init_builder.py` (신규) — 24개 단위 테스트 (NFS/CephFS sentinel, tee/dev/console, _rc 패턴, mount명령, progress마커)
- [x] `tests/test_neutron_create_port.py` (신규) — 5개 단위 테스트
- [x] `tests/test_ephemeral_build_orchestration.py` (신규) — 5개 단위 테스트 (성공/실패/indeterminate/port→rule 순서)
- [x] `tests/test_library_builder.py` — `_build_worker` 테스트를 `start_ephemeral_build` 호출로 업데이트
- [x] `tests/test_ephemeral_builder_vm.py` — outdated `test_raises_without_floating_network` 제거 (708df70에서 내부 IP fallback으로 변경되어 더 이상 유효하지 않음)

### 58.3 설계 원칙

- **Sentinel-SoT**: `::AFTERGLOW::SUCCESS/FAILURE::<build_token>` — token-unique, `nova.get_console_output(length=None)` 으로 회수
- **Port 사전 생성**: Manila access rule IP를 VM 생성 전에 예약 → race-free
- **indeterminate 처리**: SHUTOFF지만 sentinel 없음 → `console_log_excerpt` (마지막 2000자) DB 저장 + `cloud_init_status=indeterminate`
- **Phase 2 게이트**: NFS/CephFS 각 5회 연속 성공 + 의도된 실패 1회 + indeterminate 0회 충족 후 영구 VM 경로 삭제 진행
  → **Phase 2 완료 (2026-05-24)**: 게이트 검증 없이 즉시 삭제 진행 (사용자 확인)

### 58.4 검증

```bash
uv run pytest tests/test_cloud_init_builder.py tests/test_neutron_create_port.py tests/test_ephemeral_build_orchestration.py -q
# 30 passed in 0.20s
uv run ruff check app/services/ephemeral_build.py app/services/cloud_init_builder.py ...
# All checks passed
```

