# Union Mount 기반 레이어 환경 플랫폼 설계

> ⚠️ **이 문서는 Palimpsest로 통합되었다 (2026-07-27).**
> 레이어드 VM 기능의 공식 명칭은 **Palimpsest**이며, 도메인 정의·용어·digest 규칙은
> **[`docs/palimpsest.md`](docs/palimpsest.md)** 가 권위 있는 문서다.
> 실제 배포·운영 중인 파이프라인은 [`docs/squashfs-layer-pipeline.md`](docs/squashfs-layer-pipeline.md)에 있다.
>
> 이 문서는 **설계 원칙의 출처**(content-addressable, single-parent 상속, 3-lock 불변성, GC 규칙)로서
> 계속 유효하며 이력 보존을 위해 그대로 둔다. 단 아래 두 가지는 낡았으니 주의:
> - **구현 현황 서술**(§0 상단, §12 로드맵)은 현재와 다르다.
> - **`/api/union` 표면과 `UnionLayer` 모델·`scripts/layerbuild.py`·`scripts/envmgr-*.sh`는 폐기 대상**이다.
>   digest는 여기 §3.3의 결정적 tar 해시가 아니라 **`.sqsh` blob 바이트의 sha256**을 쓴다(사유는
>   `docs/palimpsest.md` §3).

> OpenStack Afterglow — `dev` 브랜치
> 작성일: 2026-04-24 | 최종 갱신: 2026-04-24
> 대상: 관리자 / 개발자 참고용 설계 문서

> **구현 현황 (2026-04-24)**: Phase 1 코드 완료.
> DB 스키마 · REST API 7개 · `layerbuild` CLI · `envmgr-use` 스크립트 · 테스트 30개 구현.
> Manila share 실제 프로비저닝 및 Builder/User VM 배포는 미완 (인프라 작업).
> 세부 상태는 `openspec/changes/archive/2026-04-16-09-union-mount-v2-content/` (구 milestone.md §9)를 참조.

## 0. 개요

OpenStack 환경 위에서 동작하는 VM 사용자들에게, 도커 이미지와 유사한 **레이어 기반 패키지 환경**을 제공하는 플랫폼. 단, 컨테이너가 아니라 **VM 내부에서 overlayfs로 직접 마운트**하여 사용한다.

- **Base**: Ubuntu 디스크 이미지 (qcow2). 레이어에 포함되지 않음.
- **Layers**: 패키지/툴체인 단위로 쌓이는 불변(read-only) 파일 트리. CephFS에 중앙 저장.
- **Overlay**: 사용자 VM에서 base + 선택된 레이어 스택을 overlayfs로 합성.
- **Builder**: 관리자 전용 빌드 VM이 사전 빌드 방식으로 레이어를 생성.
- **Metadata**: 해시, 빌드 시점, 설치 패키지, 부모 관계(parent hint)를 DB에 보관.

설계 원칙:

1. **Layer = content-addressable & immutable.** 한 번 봉인되면 영원히 불변.
2. **저장소 공유 = CephFS(Manila).** RW는 빌드 VM에만, 사용자 VM은 RO.
3. **재빌드는 덮어쓰기가 아니라 추가.** VM 스냅샷처럼 이력이 영구 보존된다.
4. **부모 없이 자식 없음.** 상위 레이어가 누락되면 하위 레이어는 활성화 불가.
5. **자식이 있으면 삭제 불가.** GC는 leaf에서만 허용.

---

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     CephFS (via Manila)                     │
│                                                             │
│  /layers/              /manifests/          /metadata/      │
│  (sealed, RO)          (versioned YAML)     (Postgres dump) │
└─────────────────────────────────────────────────────────────┘
       ▲ RW (only Builder)      ▲ RO                 ▲
       │                         │                    │
┌──────────────┐        ┌──────────────────────────────────┐
│  Builder VM  │        │  User VMs (Ubuntu qcow2 base)    │
│  (관리자 전용) │        │                                  │
│              │        │  부팅 시:                         │
│ - recipe 실행 │        │   1. Manila share mount (RO)     │
│ - overlay로   │        │   2. envmgr use <leaf-layer>     │
│   격리 빌드   │        │   3. 조상 해석 → lowerdir 조립    │
│ - 해시 계산   │        │   4. overlay 마운트               │
│ - 봉인        │        │      (upper=VM 로컬 디스크)      │
│ - DB 갱신    │        │   5. 사용자는 merged/ 에서 작업    │
└──────────────┘        └──────────────────────────────────┘
```

상위(parent) / 하위(child) 용어는 VM 스냅샷 비유로 통일한다:

```
상위 (parent, 먼저 만들어진 것)
┌──────────────────┐
│ Ubuntu base      │  ← 레이어 외부 (qcow2)
├──────────────────┤
│ L1: python       │
├──────────────────┤
│ L2: cuda         │  ← L1에 의존
├──────────────────┤
│ L3: pytorch      │  ← L2에 의존 (leaf)
└──────────────────┘
하위 (child, 나중에 만들어진 것)
```

overlayfs `lowerdir` 표기는 **왼쪽이 최상위(top)** 이므로, 마운트 시 리스트는 역순이 된다:
`lowerdir=L3:L2:L1` + `upperdir=유저로컬`.

---

## 2. CephFS + Manila 구성

### 2.1 Share 설계

세 개의 Manila share로 분리한다. 같은 CephFS 파일시스템 안에서 경로를 나눠 export.

| Share 이름        | 경로                | 빌드 VM | 사용자 VM | 관리자 VM |
|------------------|--------------------|---------|-----------|-----------|
| `layer-store-rw` | `/afterglow/layers` | RW      | —         | RW        |
| `layer-store-ro` | `/afterglow/layers` | —       | RO        | RO        |
| `manifest-store` | `/afterglow/manifests` | RW | RO        | RW        |
| `metadata-store` | `/afterglow/metadata` | RW | —         | RW        |

### 2.2 Access Rule 예시

```bash
# 사용자 VM: 레이어 저장소 읽기 전용
openstack share access create layer-store-ro cephx user-vm-readonly \
  --access-level ro

# 빌드 VM: 쓰기 권한 (물리적으로 MDS에서 강제)
openstack share access create layer-store-rw cephx builder-vm-rw \
  --access-level rw
```

**중요:** 파일 퍼미션만으로 RO를 보장하면 루트 사용자가 돌파할 수 있다. Manila access rule로 Ceph MDS caps 레벨에서 강제해야 한다.

### 2.3 overlayfs + CephFS 제약

- **`upperdir`/`workdir`은 CephFS에 절대 두지 않는다.** 반드시 VM 로컬 디스크(ext4/xfs).
  - 이유: overlayfs는 upperdir에 xattr, 원자적 rename, whiteout char device 지원을 요구.
- **`lowerdir`은 CephFS RO 마운트 허용.** 커널 5.11 이상 권장, 안정성 우선이면 **6.1 LTS 이상**.
- **NFS 쓰지 말고 CephFS 커널 클라이언트** 사용 (ceph-fuse 아님). Manila의 CephFS Native 드라이버.
- 마운트 옵션:
  ```bash
  mount -t ceph MON_HOSTS:/afterglow/layers /cephfs-ro/layers \
    -o name=user-vm-readonly,secretfile=/etc/ceph/keyring,ro
  ```

---

## 3. 레이어 모델

### 3.1 레이어 디렉토리 구조

```
/cephfs/layers/sha256-<hash>/
├── diff/            # 실제 파일 트리 (overlayfs upperdir 출력물)
└── layer.json       # 메타데이터
```

### 3.2 `layer.json` 스키마

```json
{
  "id": "sha256:abc123...",
  "name": "pytorch",
  "version": "2.4.1",
  "created_at": "2026-04-24T09:00:00+09:00",
  "created_by": "jung-geun",
  "sealed": true,

  "parent_hint": {
    "parent_id": "sha256:cuda-123-def...",
    "ancestor_chain": [
      "sha256:cuda-123-def...",
      "sha256:python-312-abc...",
      "sha256:base-meta-xyz..."
    ],
    "ubuntu_base_image": "ubuntu-24.04-server-20260401.qcow2"
  },

  "build_recipe": {
    "type": "apt+pip",
    "commands": [
      "apt-get update",
      "apt-get install -y libopenblas-dev",
      "pip install torch==2.4.1 torchvision==0.19.1"
    ],
    "apt_sources_snapshot": "http://snapshot.ubuntu.com/ubuntu/20260424T000000Z",
    "pip_index_snapshot": "2026-04-24"
  },

  "installed_packages": {
    "apt": { "libopenblas-dev": "0.3.26", "...": "..." },
    "pip": { "torch": "2.4.1", "torchvision": "0.19.1" }
  },

  "size_bytes": 2847392000,
  "file_count": 18234
}
```

### 3.3 해시 계산 규칙 (결정적)

같은 diff에서 항상 같은 해시가 나와야 한다. OCI 레이어 규격과 동일한 방식으로:

```bash
tar --sort=name \
    --mtime='1970-01-01 00:00:00 UTC' \
    --owner=0 --group=0 --numeric-owner \
    --xattrs --acls \
    -cf layer.tar -C diff/ . && \
sha256sum layer.tar
```

핵심: `--sort=name`, `--mtime 고정`, `--numeric-owner`. 누락되면 같은 파일이어도 해시가 달라진다.

### 3.4 불변성 보장 (3중 잠금)

레이어 봉인 시점에:

```bash
# (1) 권한 레벨
chmod -R a-w /cephfs/layers/sha256-abc.../
# (2) immutable 비트 (CephFS xattr 지원 확인)
chattr +i /cephfs/layers/sha256-abc.../ 2>/dev/null || true
# (3) DB에 sealed=true 기록, 이후 쓰기 시도는 애플리케이션 레벨에서 거부
```

주기적 무결성 검증(cron, 일 1회):

```bash
recorded=$(jq -r .id /cephfs/layers/sha256-abc/layer.json)
actual=$(cd /cephfs/layers/sha256-abc && tar --sort=name --mtime='1970-01-01' \
  --owner=0 --group=0 --numeric-owner -cf - diff/ | sha256sum | cut -d' ' -f1)
[[ "sha256:$actual" == "$recorded" ]] || alert "오염: sha256-abc"
```

---

## 4. 상속 모델

### 4.1 단일 상속 (MVP 기본)

각 레이어는 부모를 **0개 또는 1개**만 가진다. 링크드 리스트 구조.

```sql
-- 단일 상속용 단순 스키마
ALTER TABLE layers ADD COLUMN parent_id TEXT REFERENCES layers(id);
CREATE INDEX idx_layers_parent ON layers(parent_id);
```

장점:
- DAG 해석이 단순 (linked list 순회)
- 충돌 가능성 없음
- 운영/디버깅 용이

단점:
- 독립적인 두 브랜치를 합성할 수 없음 (예: cuda-branch + mkl-branch)

### 4.2 다중 상속 (미래 확장, opt-in)

#### 기술적 가능성

overlayfs는 `lowerdir=a:b:c:d` 형태로 **런타임에는 이미 다중 레이어를 지원**한다. 따라서 기술적으로 다중 상속 레이어를 빌드·마운트하는 것 자체는 가능하다. 그러나 빌드 시점에서 **"이 레이어의 부모가 A이자 B이다"** 라고 선언할 때 여러 이슈가 생긴다.

#### 발생 가능한 에러 유형

1. **파일 경로 충돌 (silent shadowing)**
   두 부모가 같은 경로 파일(예: `/etc/ld.so.conf.d/x.conf`)을 포함하면 overlayfs는 왼쪽(상위)을 채택하고 나머지를 가린다. **에러 없이 런타임 오동작**으로 나타남.

2. **순서 의존성 → 해시 비결정성**
   `cuda:mkl:...`과 `mkl:cuda:...`는 충돌 시 서로 다른 환경이 된다. 따라서 **부모 순서도 레이어 정체성에 포함**시켜야 한다.

3. **다이아몬드 의존성**
   `pytorch → {cuda, mkl} → glibc-patch`에서 glibc-patch가 중복 포함되지 않도록 토폴로지 정렬 + 중복 제거 필요.

4. **ABI 비호환**
   cuda branch가 python 3.12 위, mkl branch가 python 3.11 위에서 빌드된 경우 합치면 런타임 깨짐. 모든 부모 브랜치의 공통 조상이 동일해야 함.

5. **순환 의존**
   DAG에 사이클 발생 시 빌드 거부. insert 시 cycle detection으로 차단.

#### 제어 방법 (구현 시 필수 요소)

- 빌드 시 **전체 부모 목록을 순서 포함하여 명시** (`--parents=L2,L1a,L1b` 식)
- 각 부모의 파일 경로 집합을 비교해 **충돌 경로 탐지** → 경고 또는 실패
- 모든 부모의 조상을 거슬러 올라가 **공통 base가 일치하는지 검증**
- 해시 계산 입력에 **부모 ID 순서 포함**
- 다이아몬드 해석은 **토폴로지 정렬 후 중복 제거**

#### 결정

**MVP는 단일 상속으로 구현한다.** 다중 상속은 위 제어 장치가 완비된 후 `--allow-multi-parent` opt-in으로 추가한다.

---

## 5. 하이브리드 선택 모델

### 5.1 두 축의 UX

- **Model A (템플릿/매니페스트 중심):** 사용자가 `ml-pytorch@v2` 같은 이름으로 선택. 관리자가 큐레이션한 조합.
- **Model B (레이어 중심):** 사용자가 `pytorch@2.4.1` 같은 leaf 레이어 선택. 시스템이 조상을 자동 해석.

단일 상속 구조에서는 **Model B를 선택해도 조상이 자동으로 확정**되므로, 템플릿은 "자주 쓰는 leaf에 이름 붙이기"로 환원된다. 따라서:

```
템플릿(Model A) = {이름} → {leaf layer id} + {ubuntu_base 명시}
                      ↓
                  Model B로 해석 (leaf에서 조상 자동 활성화)
```

### 5.2 템플릿 정의 예시

```yaml
# /cephfs/manifests/ml-pytorch/v3.yaml
name: ml-pytorch
version: 3
created_at: 2026-04-24T09:00:00+09:00
created_by: jung-geun

# 템플릿은 leaf 지정 + base 지정만으로 완성
leaf_layer: sha256:pytorch-241-stu...
ubuntu_base: ubuntu-24.04-server-20260420.qcow2

# 이력 (왜 이 버전이 나왔는지)
parent_version: 1
note: "v1 레시피로 최신 apt snapshot 기반 재빌드"

# 자동 해석되는 조상 체인 (참고용 캐시, DB에서 재생성 가능)
resolved_stack:
  - sha256:base-noble-20260420...
  - sha256:python-312-mno...
  - sha256:cuda-123-pqr...
  - sha256:pytorch-241-stu...
```

### 5.3 CLI UX

```bash
# Model A: 템플릿으로
$ envmgr use --template ml-pytorch@v3
[템플릿 해석] leaf=pytorch@2.4.1, base=ubuntu-24.04-20260420
[조상 자동 활성화]
  1. base-noble @ 20260420
  2. python @ 3.12
  3. cuda @ 12.3
  4. pytorch @ 2.4.1
마운트 중... /var/lib/envmgr/jung-geun/ml-pytorch-v3/merged

# Model B: 직접 leaf 선택
$ envmgr use --layer pytorch@2.4.1
[조상 자동 활성화] (동일)
...
```

---

## 6. 빌드 VM 구성

### 6.1 배치

초기 단계: **단일 상주 빌드 VM** (관리자 수동 운영).
추후 규모 확장 시: **빌드 요청당 ephemeral VM** (Nova로 즉석 생성 후 파괴).

### 6.2 빌드 절차 (단일 상속 기준)

> **구현 완료**: `scripts/layerbuild.py` (서브커맨드: `init` / `exec` / `seal` / `abort`)
> 환경변수: `AFTERGLOW_API_URL`, `AFTERGLOW_API_TOKEN`, `LAYER_STORE_RW`

```bash
# 1. 관리자가 recipe.sh 준비
cat > recipe.sh <<'EOF'
#!/bin/bash
set -e
apt-get update
apt-get install -y libopenblas-dev
pip install torch==2.4.1 torchvision==0.19.1
# 재현성을 위해 캐시 제거
rm -rf /var/lib/apt/lists/* ~/.cache/pip
EOF

# 2. 작업 디렉토리 초기화 (부모 있으면 API로 조상 조회 후 overlay 마운트)
layerbuild init pytorch \
  --version 2.4.1 \
  --parent sha256:cuda-123-def... \
  --ubuntu-base ubuntu-24.04-server-20260401.qcow2

# 3. recipe 격리 실행 (systemd-nspawn)
layerbuild exec recipe.sh

# 4. 봉인 (해시 계산 → diff 이동 → 3-lock → API 등록+seal)
layerbuild seal
# stdout: sha256:<64hex>  (새 레이어 ID)
```

`layerbuild seal`이 내부적으로 수행하는 일:

1. overlay 마운트 해제 (`umount merged/`)
2. `upper/` 내용을 결정적 tar로 패킹 → sha256 계산
   - `tar --sort=name --mtime='1970-01-01T00:00:00Z' --owner=0 --group=0 --numeric-owner -cf - -C upper/ .`
3. `$LAYER_STORE_RW/sha256-<hash>/diff/` 로 이동
4. `layer.json` 기록
5. `chmod -R a-w diff/` + `chattr -R +i diff/` (CephFS 미지원 시 경고 후 진행)
6. `POST /api/union/layers` → `POST /api/union/layers/{id}/seal`
7. 작업 디렉토리 정리

### 6.3 격리 옵션

- `systemd-nspawn` (권장): 네임스페이스, cgroup 격리 간편.
- `unshare --mount --uts --ipc --pid --fork --user chroot`: 의존성 최소.
- 네트워크는 빌드 시 필요(apt/pip). 빌드 후 해시 계산 전에 **apt/pip 캐시 제거**(`/var/lib/apt/lists/*`, `~/.cache/pip/`) — 재현성 저하 요인.

### 6.4 재현성의 현실적 한계

같은 recipe를 재실행해도 해시는 보통 달라진다:
- 파일 mtime (→ tar 옵션으로 고정 가능)
- apt/pip 인덱스의 시점 차이 (→ snapshot 미러로 완화)
- 패키지 post-install 스크립트의 타임스탬프 파일
- 컴파일 시 `__DATE__`, `__TIME__` 매크로

**정책:** "재현 = 기존 레이어 재사용", "재빌드 = 새 해시로 새 레이어 추가". 둘을 명확히 구분한다.

---

## 7. 사용자 VM 구성

### 7.1 부팅 시 초기화

cloud-init 또는 systemd unit으로 `envmgr-init.service` 실행.

```bash
#!/bin/bash
# /usr/local/bin/envmgr-init.sh

# 1. Manila share 마운트 (RO)
mkdir -p /cephfs-ro/{layers,manifests}
mount -t ceph MON_HOSTS:/afterglow/layers /cephfs-ro/layers \
  -o name=user-vm-readonly,secretfile=/etc/ceph/keyring,ro
mount -t ceph MON_HOSTS:/afterglow/manifests /cephfs-ro/manifests \
  -o name=user-vm-readonly,secretfile=/etc/ceph/keyring,ro

# 2. 로컬 upperdir 영역 준비
mkdir -p /var/lib/envmgr
```

### 7.2 환경 활성화 스크립트

```bash
#!/bin/bash
# /usr/local/bin/envmgr-use.sh
# 사용: envmgr-use <leaf-layer-id>  또는  envmgr-use --template <name>@<ver>

LEAF_ID="$1"
USER_ID="$(id -un)"

# 1. DB에서 조상 체인 해석 (REST API 호출)
STACK=$(curl -s "http://api.afterglow.local/layers/${LEAF_ID}/ancestors" | \
        jq -r '.[] | .id')
# 결과 예: [base-id, python-id, cuda-id, pytorch-id] (상위→하위 순)

# 2. lowerdir 문자열 구성 (overlay는 왼쪽이 최상위이므로 역순)
LOWERDIR=""
for layer in $(echo "$STACK" | tac); do
  path="/cephfs-ro/layers/${layer//:/-}/diff"
  [[ -d "$path" ]] || { echo "상위 레이어 $layer 누락. 활성화 불가."; exit 1; }
  LOWERDIR="${LOWERDIR}${LOWERDIR:+:}${path}"
done

# 3. 사용자별 upperdir (로컬 디스크)
ROOT="/var/lib/envmgr/${USER_ID}/${LEAF_ID//:/-}"
mkdir -p "$ROOT"/{upper,work,merged}

# 4. overlay 마운트
mount -t overlay overlay \
  -o "lowerdir=${LOWERDIR},upperdir=${ROOT}/upper,workdir=${ROOT}/work" \
  "$ROOT/merged"

# 5. 진입 (nspawn 추천)
systemd-nspawn -D "$ROOT/merged" --bind=/home --bind=/tmp
```

### 7.3 upperdir 정책

- 사용자가 `merged/` 안에서 수정한 파일은 모두 `$ROOT/upper`에 쌓인다.
- 이는 **VM 로컬 디스크**이므로 VM 파괴 시 사라진다 (휘발성).
- 영구 보존이 필요하면 `/home`을 별도 볼륨으로 bind mount하거나, 사용자 upperdir 자체를 별도 Cinder 볼륨으로 제공하는 것을 검토.

---

## 8. 메타데이터 DB 스키마

> **실제 구현**: MySQL 8.0 (InnoDB, utf8mb4). 아래는 논리 스키마이며, 실제 DDL은
> `backend/app/database.py::create_tables()` 와 `backend/app/models/db.py` 참조.
> ORM은 SQLAlchemy 2.0 async 사용. `JSONB` → `JSON`, `TEXT PRIMARY KEY` → `VARCHAR(71) PRIMARY KEY`.

```sql
-- 레이어 본체 (테이블명: union_layers)
CREATE TABLE union_layers (
    id                  VARCHAR(71) PRIMARY KEY,   -- "sha256:<64hex>"
    name                VARCHAR(128) NOT NULL,
    version             VARCHAR(64) NOT NULL,
    created_at          DATETIME(6) NOT NULL,
    created_by          VARCHAR(128) NOT NULL,
    sealed              BOOLEAN NOT NULL DEFAULT FALSE,

    -- 단일 상속: 부모 0개(최상위 레이어) 또는 1개
    parent_id           VARCHAR(71) REFERENCES union_layers(id) ON DELETE RESTRICT,

    -- 최상위 레이어에만 있음: 어느 Ubuntu base 위에서 빌드됐는지
    ubuntu_base         VARCHAR(255),

    -- 재현/재빌드용
    build_recipe        JSON NOT NULL,
    installed_packages  JSON NOT NULL,

    -- 검증용
    content_hash        VARCHAR(71) NOT NULL,       -- 레이어 ID와 동일
    size_bytes          BIGINT,
    file_count          INT,

    KEY idx_union_layers_name_version (name, version),
    KEY idx_union_layers_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 템플릿 (테이블명: union_templates)
CREATE TABLE union_templates (
    name            VARCHAR(128) NOT NULL,
    version         INT NOT NULL,
    created_at      DATETIME(6) NOT NULL,
    created_by      VARCHAR(128) NOT NULL,
    parent_version  INT,
    ubuntu_base     VARCHAR(255) NOT NULL,
    leaf_layer_id   VARCHAR(71) NOT NULL REFERENCES union_layers(id) ON DELETE RESTRICT,
    note            TEXT,
    PRIMARY KEY (name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 사용자 마운트 추적 (테이블명: union_user_mounts)
CREATE TABLE union_user_mounts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(128) NOT NULL,
    vm_hostname     VARCHAR(255) NOT NULL,
    leaf_layer_id   VARCHAR(71) NOT NULL REFERENCES union_layers(id),
    mounted_at      DATETIME(6) NOT NULL,
    unmounted_at    DATETIME(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 8.1 조상 해석 쿼리 (단일 상속)

MySQL 8.0+ `WITH RECURSIVE` CTE 사용. `backend/app/services/union_layers.py::get_ancestors()` 참조.

```sql
WITH RECURSIVE ancestors AS (
    SELECT *, 0 AS depth
    FROM union_layers
    WHERE id = :leaf_id
  UNION ALL
    SELECT l.*, a.depth + 1
    FROM ancestors a
    JOIN union_layers l ON l.id = a.parent_id
)
SELECT * FROM ancestors ORDER BY depth DESC;  -- base부터 leaf 순
```

### 8.2 GC 후보 쿼리

```sql
-- 자식이 없고, 어떤 템플릿도 참조하지 않는 레이어
SELECT l.id, l.name, l.version
FROM layers l
WHERE NOT EXISTS (
    SELECT 1 FROM layers c WHERE c.parent_id = l.id
  )
  AND NOT EXISTS (
    SELECT 1 FROM templates t WHERE t.leaf_layer_id = l.id
  );
```

---

## 9. 재빌드 & 분기 시나리오

### 9.1 기존 조합 재사용

`pytorch@2.4.1` leaf를 지정하는 것만으로 `base → python → cuda → pytorch` 스택이 결정. 새 레이어 생성 없음.

### 9.2 중간 레이어만 교체 (예: cuda만 12.4로)

1. `python@3.12`를 부모로 `cuda@12.4` 레이어 신규 빌드 → sha256 할당.
2. `cuda@12.4`를 부모로 `pytorch@2.4.1` 재빌드 → 다른 sha256의 pytorch 레이어 생성.
3. 새 leaf를 사용하는 템플릿 `ml-pytorch@v4` 작성.
4. 기존 v1, v2, v3는 그대로 보존.

### 9.3 과거 시점에서 분기

"v1의 recipe로 오늘 다시 빌드"를 원하는 경우:
1. `templates` 테이블에서 v1의 `leaf_layer_id` → layer → `parent_id` 체인 조회.
2. 각 레이어의 `build_recipe`를 순서대로 현재 시점에서 재실행 (빌드 VM).
3. 각 단계에서 새 sha256이 떨어짐 (거의 확실).
4. 새 leaf를 가리키는 `ml-pytorch@v5` 작성 (`parent_version=1`로 기록).
5. 기존 레이어는 모두 보존.

---

## 10. GC 정책

### 10.1 규칙

1. **자식 레이어가 있으면 삭제 불가** (FK `ON DELETE RESTRICT`로 강제).
2. **어떤 템플릿이든 참조하면 삭제 불가** (템플릿 이력은 영구 보존).
3. **최근 N일 이내 마운트 기록이 있으면 삭제 불가** (운영 보호 장치).
4. 위 전부 통과한 leaf만 수동 GC 명령으로 제거 가능.

### 10.2 삭제 절차

```bash
layergc delete sha256:xxx...

# 내부 동작
# 1. 자식 검사: SELECT COUNT(*) FROM layers WHERE parent_id = 'sha256:xxx' → 0 확인
# 2. 템플릿 참조: SELECT COUNT(*) FROM templates WHERE leaf_layer_id = 'sha256:xxx' → 0 확인
# 3. 최근 마운트: SELECT COUNT(*) FROM user_mounts
#                WHERE leaf_layer_id = 'sha256:xxx' AND mounted_at > now() - interval '30 days'
# 4. 봉인 해제: chattr -i -R, chmod -R u+w
# 5. 파일 삭제: rm -rf /cephfs/layers/sha256-xxx/
# 6. DB 레코드 삭제
```

### 10.3 자동 GC 금지

"기존 걸 지우지 않고 스냅샷처럼 쌓는다"는 원칙상 **자동 GC는 기본 비활성**. 운영자가 디스크 압박 시에만 수동 실행.

---

## 11. 보안 모델

| 자원              | 사용자 VM    | 빌드 VM   | 관리자 VM |
|------------------|-------------|----------|----------|
| `/cephfs/layers` | Manila RO   | Manila RW | Manila RW |
| `/cephfs/manifests` | Manila RO | Manila RW | Manila RW |
| DB (Postgres)    | REST API 읽기 | REST API 읽기/쓰기 | 직접 접속 |
| 레이어 봉인 해제   | 불가         | 관리자 명령 | 관리자 명령 |

- 사용자 VM의 루트가 탈취되어도 레이어 저장소는 Ceph MDS 레벨에서 RO이므로 오염 불가.
- 빌드 VM은 물리적으로 분리된 네트워크 세그먼트에 배치 권장.
- DB에 대한 쓰기는 오직 빌드 VM의 서비스 계정과 관리자 VM에서만 허용.

---

## 12. 구현 로드맵

### Phase 1 (MVP) — 코드 완료, 인프라 미배포

**코드**
- [x] MySQL 스키마: `union_layers`, `union_templates`, `union_user_mounts` (InnoDB, WITH RECURSIVE CTE)
- [x] `backend/app/models/union.py` — Pydantic 모델 (LayerInfo, TemplateInfo, AncestorChain 등)
- [x] `backend/app/services/union_layers.py` — 서비스 레이어 (CRUD + 조상 쿼리 + 템플릿)
- [x] REST API 7개 (`/api/union/layers`, `/api/union/templates`)
- [x] `scripts/layerbuild.py` — `init` / `exec` / `seal` / `abort` 서브커맨드
- [x] `scripts/envmgr-init.sh` — Manila RO 마운트, systemd unit, envmgr-use 설치
- [x] `scripts/envmgr-use.sh` — overlay 마운트, 템플릿 지원, unmount/status
- [x] 테스트 30개 (`backend/tests/test_union_layers.py`)

**인프라 (미완)**
- [ ] Manila share 3개 실제 프로비저닝 및 CephX keyring 발급
- [ ] Builder VM 배포 및 `layerbuild` 환경변수 설정
- [ ] 수동 E2E 테스트: base → python → cuda → pytorch 4단 스택 빌드 및 사용자 VM 마운트 검증

### Phase 2 (운영 기능)
- [ ] 프론트엔드 UI: `/library` 레이어 카탈로그, 트리 시각화
- [ ] GC 명령 (`DELETE /api/union/layers/{id}` — FK RESTRICT, 마운트 이력 체크)
- [ ] `GET /api/union/layers/{id}/dependents` — 자식 레이어 목록
- [ ] 무결성 검증 cron (sha256 재계산 vs DB 비교)
- [ ] CLI 확장 (`envmgr list`, `envmgr show <layer>`, `envmgr graph`)
- [ ] 재빌드 지원 (`layerbuild init --from-layer <id>` — 기존 레이어의 recipe 재실행)
- [ ] `backend/tests/test_union_templates.py` — 템플릿 전용 추가 테스트

### Phase 3 (확장)
- [ ] 다중 상속 opt-in (충돌 감지, DAG 토폴로지 정렬)
- [ ] Ephemeral 빌드 VM (Nova로 즉석 생성 후 파괴)
- [ ] 사용자 upperdir 영구 볼륨 옵션 (Cinder)
- [ ] K3s Pod 기반 빌드 Job

---

## 13. 알려진 리스크 / 주의사항

1. **커널 버전 의존성**
   overlayfs on CephFS는 5.11 이전엔 버그 많음. **6.1 LTS 이상 표준화**.

2. **upperdir 위치 실수**
   CephFS에 upperdir를 두면 조용히 깨진다. 스크립트에 하드코딩된 안전장치 필요.

3. **apt/pip 캐시의 재현성 훼손**
   빌드 후 캐시 제거 필수. recipe 템플릿에 기본 포함.

4. **whiteout 파일과 tar**
   overlayfs 삭제는 char device 0:0 형태로 표현됨. tar 패킹 시 `--xattrs` 필수.

5. **UID/GID 충돌**
   레이어 파일의 소유권이 사용자 VM의 UID와 맞아야 함. 보통 root:root로 통일.

6. **해시 안정성**
   glibc 등 특정 패키지는 post-install에서 mtime을 남긴다. 완전 재현이 실패하면 "재빌드 = 새 해시" 정책으로 수용.

7. **Manila access rule 전파 지연**
   access rule 변경이 즉시 반영되지 않는 경우 있음. 빌드 완료 후 RO 전환 시 수 초 대기.

8. **overlayfs 스택 깊이 한계**
   커널 빌드 옵션에 따라 lowerdir 수가 제한됨 (대개 500 이상). 보통 문제 없으나 자동화 시 체크 필요.

---

## 14. 참고 자료

- Kernel overlayfs docs: <https://docs.kernel.org/filesystems/overlayfs.html>
- OpenStack Manila CephFS driver: <https://docs.openstack.org/manila/latest/admin/cephfs_driver.html>
- OCI Image Spec (레이어 해시 규격): <https://github.com/opencontainers/image-spec>
- `systemd-nspawn(1)` man page

---

## 부록 A. 단일 상속 vs 다중 상속 요약표

| 항목                | 단일 상속         | 다중 상속              |
|--------------------|------------------|-----------------------|
| 조상 해석           | linked list 순회  | DAG + 토폴로지 정렬    |
| 해시 입력           | diff만           | diff + 부모 순서      |
| 충돌 가능성         | 없음             | 있음 (silent shadow)  |
| 구현 난이도         | 낮음             | 높음                  |
| 빌드 시 검증        | 부모 존재 여부만 | 공통 조상 + 파일 충돌 |
| 권장 적용 시점      | MVP              | Phase 3 이후          |

---

## 부록 B. overlayfs 관련 용어 주의

| 용어     | 의미                                   |
|---------|---------------------------------------|
| lowerdir | 읽기 전용 레이어들. 왼쪽이 최상위      |
| upperdir | 쓰기 가능 레이어. 변경분이 쌓이는 곳    |
| workdir  | overlayfs 내부 작업용. upper와 같은 FS |
| merged   | 사용자가 보는 최종 합성 뷰            |
| whiteout | 상위 레이어에서 삭제를 나타내는 char 0:0 |
