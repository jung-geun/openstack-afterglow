# Palimpsest — 레이어드 VM 통합

## Why

afterglow에는 레이어 서브시스템이 **3세대 공존**하고 있어, 새 기능을 붙일 때마다 어느 것을 확장할지가
불명확하고 실제로 세대가 하나 더 늘어날 위험이 있다.

| 세대 | 모델 | API | 상태 |
|------|------|-----|------|
| 1세대 "library" | `LibraryRecipe` / `LibraryBuild` / `LibraryCatalog` | `/api/v1/libraries` | VM 생성 위저드가 사용 중 |
| 2세대 "union" | `UnionLayer` / `UnionTemplate` / `UnionUserMount` | `/api/v1/union` (라우트 21개) | 코드만 존재, 인프라 미배포 — 사실상 사문 |
| 3세대 "squashfs" | `LayerBuild` / `LayerConsume` / `LayerArtifact` / `LayerProfile` | `/api/v1/admin/libraries`, `/api/v1/libraries/squashfs` | **실제 배포·운영 중** |

또한 운영 중인 3세대에는 **콘텐츠 해시가 없다**. `LayerArtifact`는 int PK + `parent_id`(INT) + `sqsh_filename`
으로 식별되며 digest 컬럼이 없다. 해시 계산 코드는 미배포 2세대 CLI(`scripts/layerbuild.py`)에만 있고,
`union_layers.py`는 클라이언트가 보낸 `content_hash`를 그대로 신뢰한다.

이 상태에서는 요구되는 "해시로 레이어를 검색·관리한다", "부모 레이어를 추적해 한 번에 다운로드한다"가
성립하지 않는다.

## Goal

레이어드 VM 제공 기능을 **Palimpsest**로 명명·통합하고, 운영 중인 3세대 파이프라인에 콘텐츠 주소 정체성을
도입해 Dockerfile 빌드 · 레이어 허브 · 로컬 KVM 런타임의 공통 토대를 만든다.

## Scope

- **명명·통합**: 3세대 squashfs 파이프라인을 Palimpsest 코어로 흡수. 2세대 `/api/v1/union` 표면과
  `union_layers.py`·`scripts/layerbuild.py`·`scripts/envmgr-*.sh` 폐기(테이블은 보존). 1세대
  `LibraryCatalog`/`/api/v1/libraries`는 범위 밖으로 보존.
- **콘텐츠 주소화**: `layer_artifacts`에 `blob_digest`(sha256) · `blob_md5` · `config_digest` · `chain_id` ·
  `digest_state` 추가. digest는 `.sqsh` blob 바이트의 sha256. 신규 빌드는 빌드 VM에서 계산하고,
  기존 행은 상주 SSH Builder VM 경유 백필.
- **API 표면**: `/api/v1/palimpsest/…` 단독 마운트 + `_AUDIT_PREFIX_MAP` 등록. 기존 두 경로는 같은 서비스
  seam을 호출하는 dual-mount로 유지 후 프론트 전환 완료 시 제거.
- **허브**: `HubBlobStore`(local_path 드라이버) 위에 업로드 세션 · digest 검색 · blob 스트리밍 ·
  부모 체인 OCI image-layout 번들 export/import · pull.
- **Dockerfile 빌드 확장**: 기존 `dockerfile_import.py`에 `DockerfileSource` 추상화를 넣어 사용자 업로드
  (inline) Dockerfile 수용. `FROM`에서 부모 레이어 digest 해석. `chain_id` 기반 빌드 캐시.
- **로컬 KVM 런타임**: libvirt + NoCloud seed ISO로 로컬 VM 생성, 호스트 레이어 경로를 virtio-blk로 부착.

## Non-goals

- OCI Distribution Spec `/v2/` 호환 레지스트리 구현 (자체 REST + OCI image-layout **번들 포맷**만 채택).
- 레이어 서명·신뢰 체인(cosign 등).
- `layer_artifacts` 등 **기존 DB 테이블 리네임** (비용 대비 효과 없음. 신규 테이블만 `palimpsest_*`).
- 1세대 `LibraryCatalog`/`/api/v1/libraries` 재설계.
- **OpenStack에서 virtio-blk/virtio-scsi로 레이어를 부착하는 코드** — 설계·구현 계획만 확정하고 착수하지
  않는다. 운영 경로는 NFS를 유지한다. 착수 게이트는 "Cinder 백엔드가 Ceph RBD인가" 확인 결과다
  (Cinder는 read-only 멀티어태치를 지원하지 않아 레이어 볼륨 1개를 여러 VM에 RO 공유할 수 없다).
- squashfs → EROFS 전환 (레이어 수가 커질 때 재검토).

## Acceptance

- 사용자 대면 명칭·문서가 Palimpsest로 통일되고, 3세대의 관계가 `docs/palimpsest.md`에 명시된다.
- 신규 레이어 빌드가 `blob_digest`/`blob_md5`/`chain_id`를 `digest_state='ready'`로 기록한다.
- 기존 artifact를 백필해도 소비 VM 생성 경로가 그대로 동작한다(digest 없는 행도 소비 가능).
- digest prefix / md5 / chain_id로 레이어를 검색할 수 있다.
- 임의 레이어의 부모 체인을 OCI image-layout 번들 **하나**로 내려받고, 다른 사이트에 import했을 때
  모든 blob digest가 보존된다.
- 사용자 업로드 Dockerfile로 레이어 체인을 빌드할 수 있고, 동일 명령 시퀀스 재요청 시 빌드가 생략된다.
- 로컬 KVM 호스트에서 허브 번들을 펼쳐 VM을 띄우고 overlay merged에서 패키지를 실행할 수 있다(수동 검증).
- 기존 레이어 테스트(`test_layer_ops`, `test_layer_build`, `test_layer_consume`, `test_dockerfile_import`,
  `test_recipe_blocks`, `test_common_libraries_squashfs`, `test_cloud_init_builder`)가 전부 그대로 통과한다.
