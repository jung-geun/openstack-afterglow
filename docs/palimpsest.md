# Palimpsest — 레이어드 VM

> afterglow가 제공하는 **레이어드 VM** 기능의 공식 명칭.
> 작성일: 2026-07-27 | 대상: 관리자 / 개발자

Docker 이미지처럼 패키지 환경을 레이어로 쌓되, 컨테이너가 아니라 **VM 안에서 OverlayFS로 직접 마운트**한다.
지운 글 위에 새로 쓴 층이 비쳐 보이는 양피지(palimpsest)에서 이름을 따왔다.

---

## 1. 왜 이 문서가 필요한가 — 레이어 서브시스템 3세대

afterglow에는 역사적으로 레이어 관련 코드가 **세 갈래**로 자라났다. 이 관계를 모르면 어느 코드를 고쳐야
하는지 판단할 수 없다.

| 세대 | 모델 (`backend/app/models/db.py`) | 주요 코드 | API | 상태 |
|------|-----------------------------------|-----------|-----|------|
| 1세대 "library" | `LibraryRecipe`(236) `LibraryBuild`(261) `LibraryCatalog`(694) | `services/library_builder.py`, `library_recipes.py` | `/api/v1/libraries` | VM 생성 위저드가 사용 중 |
| 2세대 "union" | `UnionLayer`(492) `UnionTemplate`(542) `UnionUserMount`(562) | `services/union_layers.py`, `scripts/layerbuild.py`, `scripts/envmgr-*.sh` | `/api/v1/union` | 코드만 존재, 인프라 미배포 |
| 3세대 "squashfs" | `LayerBuild`(296) `LayerConsume`(350) `LayerArtifact`(373) `LayerProfile`(469) | `services/layer_build.py`, `layer_builder.py`, `recipe_blocks.py`, `cloud_init_builder.py`, `dockerfile_import.py`, `builder_vm.py`, `manila.py` | `/api/v1/admin/libraries`, `/api/v1/libraries/squashfs` | **실제 배포·운영 중** |

### Palimpsest의 처리 방침

| 대상 | 처리 |
|------|------|
| 3세대 squashfs 파이프라인 | **흡수** — Palimpsest 코어다. 코드 경로와 스토리지 전략을 유지한 채 확장한다 |
| 2세대 union | **폐기** — `/api/v1/union` 표면과 `union_layers.py`·`layerbuild.py`·`envmgr-*.sh`를 제거한다. 다만 `union.md`의 설계 원칙(content-addressable, single-parent, 3-lock, GC 규칙)과 결정적 해시 개념은 Palimpsest로 이식한다. `union_*` 테이블은 데이터 보존을 위해 남긴다 |
| 1세대 library | **보존, 범위 밖** — VM 생성 위저드가 쓰는 카탈로그다. 건드리지 않는다 |

> **읽는 순서**: 이 문서 → `docs/squashfs-layer-pipeline.md`(운영 중인 파이프라인의 상세) → `union.md`
> (설계 원칙의 출처, 단 구현 현황 서술은 낡았음).

---

## 2. 용어

| 용어 | 의미 |
|------|------|
| **레이어(layer)** | 불변(read-only) 파일 트리 하나. squashfs `.sqsh` 파일로 봉인되어 레이어 전용 Manila NFS share에 저장된다 |
| **digest** | 레이어의 정체성. `.sqsh` blob 바이트의 sha256 → `sha256:<64hex>` |
| **chain_id** | 스택 전체의 정체성. `chain_id(root)=blob_digest(root)`, `chain_id(n)=sha256(chain_id(n-1) + " " + blob_digest(n))` |
| **부모(parent)** | 이 레이어가 그 위에 쌓인 직계 상위 레이어. 단일 상속(0개 또는 1개) |
| **봉인(seal)** | 빌드 완료 후 share의 RW access rule을 회수해 RO 전용으로 만드는 것 |
| **프로파일(profile)** | 함께 마운트할 레이어 집합에 이름을 붙인 것 (`LayerProfile`) |
| **소비(consume)** | 프로파일을 마운트한 VM을 만드는 것 (`LayerConsume`) |
| **허브(hub)** | 레이어를 digest로 저장·검색·배포하는 저장소 |
| **번들(bundle)** | 부모 체인 전체를 담은 OCI image-layout 디렉터리/tar |

---

## 3. digest 규칙

**digest = `.sqsh` blob 바이트 자체의 sha256.**

`union.md` §3.3이 제안한 "결정적 tar 해시"(같은 recipe → 같은 해시)를 채택하지 않는다. `union.md` §6.4가
스스로 결론냈듯 같은 recipe를 재실행해도 해시는 보통 달라지기 때문이다. blob digest는 대신 이 셋을 준다:

1. 이미 share에 존재하는 산출물에 그대로 적용 가능 → **백필 가능**
2. 다운로드 후 재계산만으로 **검증 가능**
3. OCI blob digest와 의미론이 같아 허브 번들이 **OCI image-layout에 그대로 매핑**

파생 값:

- `config_digest` — 레이어 메타 JSON(name/kind/ubuntu_base/packages/parent digest…)을 `sort_keys` 정규화한 sha256.
- `chain_id` — 위 표 참조. "이 스택 전체가 동일한가"를 O(1)로 비교하므로 Dockerfile 빌드 캐시와
  프로파일 중복 제거의 근거가 된다.

`blob_md5`는 외부 도구 호환을 위한 **보조 검색 키**다. 식별과 무결성의 권위는 언제나 sha256이며,
md5를 보안 목적으로 쓰지 않는다.

정책은 union.md를 계승한다 — **"재현 = 기존 레이어 재사용", "재빌드 = 새 digest로 새 레이어 추가."**
기존 레이어를 덮어쓰지 않는다.

---

## 4. 저장과 마운트

### OpenStack (운영 경로)

레이어마다 전용 Manila **NFS** share를 만들고 `.sqsh`를 넣는다. 소비 VM은 cloud-init으로 각 share를
RO 마운트 → `.sqsh` loop-mount → OverlayFS 합성한다. 상세는 `docs/squashfs-layer-pipeline.md`.

```
afterglow-layer-<name>-<token>/
  images/<name>-<ts>.sqsh
         <name>-latest.sqsh
  _build_logs/…
```

### 로컬 KVM

허브 번들을 호스트에 펼친 뒤 virtio-blk로 붙인다.

```
/var/lib/palimpsest/layers/sha256/<hex>/layer.sqsh
                                       layer.json
```

### virtio-blk / virtio-scsi (OpenStack) — 미구현

**Cinder는 read-only 멀티어태치를 지원하지 않는다**(2차 이후 attach는 RW, read-only 정책은 future work,
암호화 볼륨 multiattach 불가). 따라서 레이어 볼륨 1개를 여러 소비 VM에 RO로 공유할 수 없고, virtio는
NFS의 마운트 옵션 교체가 아니라 **다른 스토리지 토폴로지**(VM당 볼륨)다.

착수 게이트는 **Cinder 백엔드가 Ceph RBD인가**이다. RBD면 COW clone으로 저렴하지만, 아니면 VM당 전체 복사가
되어 비현실적이다. 구현 계획은 `openspec/changes/palimpsest-layered-vm/` Phase 6 참조.

---

## 5. OverlayFS 제약 (변하지 않는 규칙)

- **`upperdir`/`workdir`은 반드시 VM 로컬 디스크(ext4/xfs).** CephFS/NFS에 두면 조용히 깨진다 —
  overlayfs는 upperdir에 xattr, 원자적 rename, whiteout char device를 요구한다.
- `lowerdir`는 RO 네트워크 파일시스템 가능. 커널 **6.1 LTS 이상** 권장.
- `lowerdir=A:B:C`에서 **왼쪽이 최상위**다. 조상 체인(루트→리프)을 넘길 때 역순이 된다.
- 삭제는 char device 0:0(whiteout)으로 표현되므로 tar 패킹 시 `--xattrs` 필수.

---

## 6. 관련 문서

- `docs/squashfs-layer-pipeline.md` — 운영 중인 파이프라인의 빌드/소비 흐름, DB 모델, 버그 이력
- `union.md` — 설계 원칙의 출처(content-addressable, single-parent, 3-lock, GC). 구현 현황 서술은 낡음
- `openspec/changes/palimpsest-layered-vm/` — 통합 작업의 proposal과 Phase별 tasks
