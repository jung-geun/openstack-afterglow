## Implementation Tasks

> 마이그레이션 번호 주의: 착수 시점에 `053`~`056`이 커밋되지 않은 chat 플랫폼 작업에 선점돼 있다.
> Palimpsest는 **057**부터 사용하고, 파일 생성 직전 `ls backend/migrations/`로 빈 번호를 재확인한다.

### Phase 0 — OpenSpec change + Palimpsest 명명 (코드 동작 불변)

- [x] `openspec/changes/palimpsest-layered-vm/{proposal.md,tasks.md}` 생성 (rapid 스키마)
- [x] `docs/palimpsest.md` — 도메인 정의(3세대 흡수/폐기/보존 표), 용어집, digest 규칙, OverlayFS 제약
- [x] `union.md` · `docs/squashfs-layer-pipeline.md` 상단에 "Palimpsest로 통합됨" 안내 추가 (내용 삭제 금지 — 이력 보존)
- [x] `CLAUDE.md` — "Union Mount 설계" 절을 "Palimpsest (레이어드 VM) 설계"로 교체, 읽는 순서 명시, 프로젝트 구조 표에 `docs/palimpsest.md` 추가
- [x] 프론트 **사용자 대면 라벨만** 교체 — `AdminSidebar.svelte` 그룹 `라이브러리`→`Palimpsest` / 항목 `라이브러리 관리`→`레이어 관리`, `routes/admin/libraries/+page.svelte` PageHeader `라이브러리 관리`→`Palimpsest 레이어 관리`. 경로·API·타입명 불변
  > **범위 정정**: `routes/dashboard/library/**` · `lib/components/library/` · `lib/components/dashboard/library/` ·
  > `lib/types/layer.ts` · `wizard/SelectTemplate.svelte`는 **2세대 union UI**다(`/api/v1/union/layers`·
  > `/api/v1/union/templates` 호출, `LayerInfo`가 `content_hash`/`file_count` 형태). Phase 2 폐기 대상이므로
  > 리브랜딩하지 않는다 — 죽을 화면에 Palimpsest 이름을 붙이면 오해만 남는다.
  > `routes/admin/layers/`는 `/admin/libraries`로 가는 308 redirect stub이라 변경 불필요.
- [x] 게이트 확인 후 커밋 (내 파일 9개만 명시적 스테이징)
  - 백엔드 pytest `3475 passed, 79 skipped` / 프론트 vitest `810 passed (160 files)`
  - `ruff check`는 `app/services/chat/durable_runs.py` I001 1건 실패 — **미커밋 병렬 chat 작업 소유**.
    `git show HEAD:…/durable_runs.py | ruff check --stdin-filename`은 `All checks passed` → HEAD는 깨끗하고
    Phase 0은 백엔드 Python 무변경. 남의 WIP를 `--fix`하지 않는다
  - 프론트 계약 테스트 `libraries-layer-workflow.test.ts`가 옛 PageHeader 문자열을 고정하고 있어 함께 갱신

### Phase 1 — 콘텐츠 주소화

- [x] `backend/migrations/057_palimpsest_content_addressing.sql` — `layer_artifacts`에 `blob_digest` VARCHAR(71) / `blob_md5` CHAR(32) / `config_digest` VARCHAR(71) / `chain_id` VARCHAR(71) / `digest_state` VARCHAR(16) DEFAULT 'pending' + 인덱스 2개. 멱등(`information_schema` 체크), prepared stmt `palimpsest_digest_stmt`
- [x] `backend/migrations/manifest.txt`에 `057-palimpsest-content-addressing|…|<sha256>` 등록
  > 커밋 시 인덱스에는 **HEAD + 057 한 줄만** 올렸다. 작업 트리 manifest 에는 커밋되지 않은 병렬 chat 작업의
  > 053~056 항목이 들어 있는데, 그 `.sql` 파일들이 커밋에 없는 채로 manifest 만 커밋되면
  > `load_manifest()` 가 "references an invalid migration path" 로 **fail-closed** 되어 부팅·테스트가 깨진다
  > (`backend/scripts/baseline_migrations.py:59`).
- [x] 🔴 배포 순서 — dev 환경에서 ORM 이 먼저 반영되어 `Unknown column 'layer_artifacts.blob_digest'` 500 이
  실제로 재현됐고, 057 적용으로 복구했다. 적용 후 ORM SELECT 성공 / 기존 4행 `pending` / 재실행 멱등 확인
- [x] `backend/app/models/db.py` `LayerArtifact`에 신규 컬럼 추가
- [x] `services/palimpsest_digest.py` 신규 — 순수 함수(`normalize_digest`, `compute_chain_id`, `compute_config_digest`, `parse_digest_sentinels`). `scripts/layerbuild.py:131-168`의 해시 개념 이식
- [x] `services/palimpsest_layers.py` 신규 — 세션이 필요한 헬퍼(`load_lineage`/`load_ancestor_chain`/`resolve_digest_fields`/`recompute_descendant_chain_ids`). `layer_ops._artifact_lineage_rows`가 이쪽에 위임하도록 통합(계보 해석 이중화 제거)
- [x] `services/recipe_blocks.py` — 5개 squashfs 레시피 전부 `mksquashfs` 직후 `sha256sum`/`md5sum`/`stat` → `::AFTERGLOW::DIGEST::layer=<name> …` sentinel 출력. `|| true` 로 감싸 **digest 계산 실패가 빌드 실패가 되지 않게** 함(`set -euo pipefail` 환경)
  > sentinel 에 **레이어 이름을 싣는다** — Dockerfile import 는 한 번의 VM 실행으로 여러 레이어를 만들고,
  > 콘솔이 잘리면 위치 기반 매핑이 조용히 어긋나 잘못된 digest 가 붙는다
- [x] `services/layer_build.py` + `services/dockerfile_import.py` — 두 artifact 생성 경로 모두 sentinel 회수 → `digest_state='ready'`. 미확보 시 `pending` 으로 기록하고 빌드는 성공 처리
- [x] `chain_id` 계산 — 루트는 자기 digest, 이후 `sha256(parent_chain + " " + digest)`. 부모가 `pending`이면 자식 `chain_id`를 **만들지 않는다**(루트 취급하면 서로 다른 스택이 같은 chain_id 를 갖게 됨)
- [x] `backend/tests/test_palimpsest_digest.py` (36 케이스) — 정규화/검증, sentinel 이름 매핑·중복 last-wins·빈 sha256 스킵·size 누락 허용, chain_id 결정성 및 부모 민감성, config_digest 키 순서 무관, `resolve_digest_fields` 4 케이스, `recompute_descendant_chain_ids` 2 케이스, 계보 순서·사이클 방어, 5개 레시피 전부 sentinel 방출 + `|| true` 보장, ORM 컬럼/인덱스 존재
- [x] `POST /api/v1/admin/palimpsest/artifacts/backfill-digest` — `services/palimpsest_backfill.py`.
      **임시 Builder VM 한 대**로 배치 전체 처리 → share RO 마운트 → 해시 → access rule/VM 회수.
      실패는 `digest_state='failed'` + 사유, 배치는 계속. 완료 후 chain_id 재계산
  > ⚠ **계획 정정**: 계획서의 "상주 SSH Builder VM 경유"는 성립하지 않는다. `builder_vm.py` 는
  > *"Ephemeral(빌드별 임시) 경로만 지원"* 이고 상주 경로는 코드에서 제거됐다.
  > `afterglow.conf.example [builder]` 의 `persistent_server_id` / `ssh_host` / `ssh_private_key` 는
  > `config.py` 에 대응 필드가 **없는 낡은 문서**다(설정 동기화 의무 위반 — 기존 상태).
  > → 별도 정리 항목으로 남긴다.
- [x] `GET /api/v1/palimpsest/layers?digest=&digest_prefix=&md5=&chain_id=&name=&kind=` + `GET /…/{id}/ancestors`
      (공개+봉인 레이어만 노출, 미공개는 존재 여부도 흘리지 않고 404)
- [x] `GET /api/v1/admin/palimpsest/artifacts` + `GET /…/digest-status` (관리자 전용 전체 조회·분포)
- [x] `main.py` 마운트 + `_AUDIT_PREFIX_MAP` 에 `/api/v1/palimpsest`, `/api/v1/admin/palimpsest` 등록
- [x] `backend/tests/test_palimpsest_api.py` (33 케이스) — 감사 매핑·라우트 v1 단독, 검색 파라미터 9종 422,
      미인증 거부, 가시성 조건 강제, 미공개 404, 관리자 3종 403, 해시 명령 인젝션 거부(export path 4종 /
      sqsh 파일명 4종), RO 마운트 고정, 백필 성공/실패/예외 시 access rule·VM 회수

### 별도 정리 (범위 밖, 발견 사항)

- [ ] `afterglow.conf.example [builder]` 의 `persistent_server_id` / `ssh_host` / `ssh_private_key` 제거 또는
      `config.py` 필드 복구 — 현재 문서와 코드가 어긋나 있다(설정 동기화 의무). 어느 쪽이 의도인지 확인 필요

### Phase 2 — `/api/v1/palimpsest` 표면 + union 폐기

- [ ] `backend/app/api/palimpsest/{layers,builds,hub,admin}.py` 신규 — 기존 서비스 함수 호출(로직 이중화 금지)
- [ ] `main.py` — `/api/v1/palimpsest/…` 마운트 + `_AUDIT_PREFIX_MAP`에 `("/api/v1/palimpsest", "palimpsest_layer")` 등록
- [ ] 기존 `/api/v1/admin/libraries`·`/api/v1/libraries/squashfs`를 같은 서비스 seam 호출 dual-mount로 유지
- [ ] 2세대 폐기 — `/api/v1/union` 마운트 제거, `app/api/union/layers.py` · `services/union_layers.py` · `scripts/layerbuild.py` · `scripts/envmgr-*.sh` 삭제. **`union_*` 테이블은 보존**(DROP 필요 시 행 수 0 확인 단계를 별도 항목으로)
- [ ] 프론트 API 호출 경로를 `/api/v1/palimpsest/…`로 전환
- [ ] 레거시 dual-mount 제거는 **프론트 전환 커밋 이후 별도 커밋**
- [ ] 테스트 — 신규 경로 계약 + (전환 전) 레거시 경로가 404가 아님을 고정

### Phase 3 — 허브

- [ ] `services/palimpsest_hub_store.py` — `HubBlobStore` 인터페이스(`open_read`/`write_stream`/`exists`/`delete`) + `local_path` 드라이버. 배치는 OCI image-layout(`<root>/blobs/sha256/<hex>`)
- [ ] `[palimpsest] hub_local_path` 설정 추가 — `config.py` + `generate_k8s.py` + `afterglow.conf.example` **3곳 동시**
- [ ] 업로드 세션 `POST/PATCH/PUT /api/v1/palimpsest/hub/uploads[/{session}]` — 선언 digest 존재 시 단축 완료, 완료 시 **수신 바이트 digest 재계산 후 불일치 폐기(fail-closed)**
- [ ] 검색 `GET /hub/layers` (q, digest, digest_prefix, md5, kind, name, chain_id, cursor)
- [ ] 상세 `GET /hub/layers/{digest}` + `GET /hub/layers/{digest}/ancestors`
- [ ] blob 스트리밍 `GET /hub/layers/{digest}/blob` (HTTP Range 지원)
- [ ] 번들 export `POST /hub/bundles` — `{refs:[digest…]}` → OCI image-layout tar 스트리밍(`oci-layout` + `index.json` + `blobs/sha256/`). layers[]는 루트→리프 순 부모 체인 전체. mediaType: config `application/vnd.afterglow.palimpsest.layer.config.v1+json`, layer `application/vnd.afterglow.palimpsest.layer.squashfs.v1`
- [ ] 번들 import `POST /hub/bundles/import` — 전 blob digest 재검증 후 등록
- [ ] `POST /hub/layers/{digest}/pull` — 허브 → 이 사이트 레이어(부모 체인 포함)
- [ ] `DELETE /hub/layers/{digest}` — 관리자. 자식 존재 시 거부(union.md §10 GC 규칙 계승)
- [ ] 인가 — 조회/다운로드는 `is_published` 또는 `project_id` 일치, 업로드/삭제는 관리자 또는 소유 프로젝트. digest path param 접근 시 소유권 검증(IDOR)
- [ ] `backend/tests/test_palimpsest_hub.py` — digest 불일치 업로드 거부, 중복 digest 단축, 번들에 조상 전부 포함, import 왕복 digest 보존, 자식 있는 레이어 삭제 거부, 타 프로젝트 404, Range 다운로드

### Phase 4 — Dockerfile 빌드 확장

- [ ] `services/dockerfile_import.py`에 `DockerfileSource` 추상화 — `github`(기존 경로 유지) / `inline`(본문 업로드, `_MAX_DOCKERFILE_BYTES` 재사용)
- [ ] `POST /api/v1/palimpsest/builds/dockerfile` — **inline 모드는 빌드 컨텍스트가 없으므로 `COPY`/`ADD` 거부**(에러에 GitHub 소스 안내)
- [ ] `FROM` 해석 — `ubuntu:24.04` → ubuntu base key(`layer_base_images.py`) / `palimpsest/<name>@sha256:<digest>` → 부모 레이어 / `scratch` 거부
- [ ] 빌드 캐시 — `step_digest = sha256(parent_chain_id + "\n" + 정규화된 instruction)`으로 기존 artifact 재사용
- [ ] 🔴 inline 경로는 임의 쉘 실행이므로 `require_admin` 유지. 일반 사용자 개방은 별도 결정(격리·쿼터·네트워크 정책 선행)
- [ ] `backend/tests/test_palimpsest_dockerfile.py` — inline COPY 거부, FROM digest 해석, 캐시 히트 시 빌드 미실행, `_UNSUPPORTED` 명령 거부 회귀, 개행/쉘 메타문자 인젝션 거부

### Phase 5 — 로컬 KVM 런타임 (CI 검증 불가)

- [ ] `services/palimpsest_kvm.py` — `libvirt-python` 드라이버(도메인 XML 생성·정의·시작·삭제)
- [ ] NoCloud seed ISO — `cloud-localds`로 `user-data`/`meta-data` 굽기. user-data는 기존 `services/cloudinit.py` + `templates/overlay_setup.sh.j2` 재사용
- [ ] 호스트 레이어 경로 규약 `/var/lib/palimpsest/layers/sha256/<hex>/layer.sqsh` (+ `layer.json`) — 허브 OCI 번들을 그대로 펼친 배치
- [ ] virtio-blk로 레이어 `.sqsh` RO 부착 → 게스트 `mount -t squashfs` → 기존 overlay 조립. 모든 보간 `shlex_quote`
- [ ] `docs/palimpsest-local-kvm-runbook.md` — 수동 검증 런북
- [ ] 단위 테스트 — libvirt XML 생성, seed ISO 인자 조립, 경로 쿼팅까지만 커버
- [ ] ⏳ 실환경 검증(수동, CI 불가) — 로컬 KVM 호스트에서 3단 스택 VM 부팅 + merged에서 패키지 실행

### Phase 6 — OpenStack virtio (계획 확정, 코드 미착수)

- [ ] ⏳ 착수 게이트 — `cinder.list_volume_types()` / `cinder.list_storage_pools()`로 백엔드 확인.
      **RBD가 아니면 착수하지 않고 "NFS 유지"를 최종 결론으로 문서화**
- [ ] ⏳ RBD인 경우: 대표 레이어 1개 clone 소요 시간 + 프로젝트 볼륨 개수 쿼터 측정
- [ ] (게이트 통과 시) `services/palimpsest_volume.py` — blob → Glance(`glance.create_image` disk_format=raw) → VM당 `cinder.create_volume_from_image` → `nova.attach_volume` + `delete_on_termination=True`, 실패 시 전량 롤백
- [ ] (게이트 통과 시) `058_palimpsest_layer_volumes.sql` + `layer_consumes.volume_ids JSON`
- [ ] (게이트 통과 시) 게스트 디바이스는 `/dev/vdX`가 아니라 `/dev/disk/by-id/virtio-${VOLUME_ID:0:20}` (scsi면 `scsi-0QEMU_QEMU_HARDDISK_…`)
- [ ] (게이트 통과 시) `[palimpsest] consume_transport`(기본 `nfs`) / `virtio_disk_bus` — 3곳 동시 갱신
- [ ] (게이트 통과 시) `backend/tests/test_palimpsest_volume.py`
