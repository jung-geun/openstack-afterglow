## Phase 55 — 영구 Builder VM + SSH 기반 라이브러리 빌드 파이프라인 (2026-05-21)

### 55.1 동기

기존 ephemeral VM + cloud-init 방식의 library_builder.py는 silent fail 지점이 다수 누적되어 빌드가 실제로 동작하지 않는 상태였다:
- `_INSTALL_SCRIPTS`에 `pytorch` 키 부재 — UI가 보내는 ID와 매핑 불일치 → "Unknown library" 없이 SHUTOFF
- `_monitor_build:573-575` — console 로그 조회 실패 시 `build_success=True`로 간주 (silent success)
- `_monitor_build:740-749` — 최상위 try/except가 모든 예외를 삼킴
- cloud-init 30분 타임아웃 안에 vllm/torch 다운로드 + CephFS write 빠듯
- SSH key_name 미주입, console 로그 2000자 truncation으로 디버깅 불가

`union.md` 원설계(service 프로젝트 영구 Builder VM 1대 + SSH 직접 명령)로 정렬해 파이프라인을 정상화한다.

### 55.2 백엔드

- [x] `backend/pyproject.toml` — `asyncssh>=2.18` 의존성 추가
- [x] `backend/app/config.py` — 영구 Builder VM SSH 설정 필드 추가:
  `builder_persistent_server_id`, `builder_ssh_user`, `builder_ssh_key_path`,
  `builder_ssh_host`, `builder_floating_network_id`, `builder_build_timeout`
- [x] `backend/app/services/ssh_executor.py` (신규) — asyncssh 기반 `run_command()`, `stream_command(line_callback)`
- [x] `backend/app/services/builder_vm.py` (신규) — `ensure_builder_vm(svc_conn)`:
  server_id 조회 → 없으면 keypair 생성, cloud-init bootstrap 부팅, FIP 할당, ACTIVE 대기, SSH 도달 확인
- [x] `backend/app/services/library_builder.py` — 대규모 재작성:
  - ephemeral VM 코드 제거 (`_create_builder_vm`, `_generate_cloudinit`, `_generate_probe_cloudinit`, `_verify_layer_accessible`, `_monitor_build`, `_cleanup_builder_resources`)
  - `start_build()` → `ensure_builder_vm()` + `stream_command()` 기반으로 교체
  - `_ssh_build_task()` 신규: RW rule 설치 → RO rule 전환 → metadata ready → set_share_public
  - `_build_ssh_command()` 신규: cephx_secret + install_script를 base64 인코딩해 shell injection 방지
  - `_INSTALL_SCRIPTS["pytorch"]` alias 추가 (UI ID 'pytorch' → 'torch' 동일 스크립트)
  - `_get_lib_size()` — pytorch 항목 추가
- [x] `backend/app/main.py` — 시작 시 `ensure_builder_vm` 백그라운드 호출 추가 (Manila 활성화 시)
- [x] `config.toml.example` — `[builder]` 섹션 SSH 설정 항목 추가
- [x] `generate_k8s.py` — 신규 builder 키 configmap 인라인에 포함

### 55.3 테스트

- [x] `backend/tests/test_ssh_executor.py` (신규) — `run_command` / `stream_command` asyncssh mock 4건
- [x] `backend/tests/test_builder_vm.py` (신규) — ACTIVE 즉시반환, 캐시 히트, SHUTOFF 재기동, `_extract_fip`, `_build_ssh_command` 7건
- [x] `backend/tests/test_library_builder.py` — 기존 ephemeral VM 테스트 제거, SSH 파이프라인 테스트로 교체:
  pytorch alias 검증, `_build_ssh_command` 6건, `start_build` 4건, 큐/워커 5건

### 55.4 검증

```bash
cd backend
pytest tests/test_ssh_executor.py tests/test_builder_vm.py tests/test_library_builder.py -v
npm run lint:backend && npm run test:all
```

실 환경 통합 검증:
1. 백엔드 재기동 후 `openstack server list --project service` → `afterglow-builder` ACTIVE + FIP 할당 확인
2. 관리자 UI에서 `python311` 빌드 → `library_builds` DB 진행률 변화 확인
3. 완료 후 `openstack share show union-prebuilt-python311` → `metadata.union_status=ready`, `is_public=True`

### 55.5 비범위

- SSE/WebSocket 진행률 실시간 푸시 (별도 milestone 항목으로 추가 예정)
- 멀티 Builder VM 풀 / 동시 빌드 수 확장 (단일 VM + asyncio.Queue 직렬화 유지)

---

