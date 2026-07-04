# squashfs + OverlayFS 레이어 파이프라인

afterglow VM에 squashfs 기반 패키지 레이어를 적용하는 독립 스캐폴드.
**Manila NFS share를 레이어 저장소로 재사용**한다.

## 디렉토리 구조

```
layers/
  build/
    build-layer-diff.sh     # (권장) OverlayFS diff 캡처 → squashfs
    build-layer.sh          # (대안) debootstrap minbase + chroot → squashfs
  vm/
    layer-activate.sh       # profile → squashfs 마운트 → OverlayFS 합성
  profiles/
    ml-worker.conf          # ML/AI 워크로드 예제
    web-server.conf         # Node.js + nginx 예제
  cloud-init/
    layer-vm.cloud-config.yaml  # VM 생성 시 user-data 템플릿
```

---

## 전체 운영 흐름

```
[ 1. 빌드 ]           [ 2. 배치 ]           [ 3. 소비 (VM) ]
빌드 머신에서          Manila NFS share       VM 부팅 시
build-layer-diff.sh → /images/<name>.sqsh → layer-activate.sh
                       /profiles/<p>.conf      ↓
                                            squashfs loop mount (RO)
                                               ↓
                                            OverlayFS 합성
                                            (target = /usr 또는 /opt/layers/merged)
                                               ↓
                                            재부팅: systemd unit이 재현
```

---

## 1. Manila NFS share를 레이어 저장소로 사용하기

afterglow는 이미 Manila(OpenStack shared filesystem)를 사용한다.
기존 Manila **NFS share**를 레이어 이미지 저장소(`/images/`, `/profiles/`)로 재활용한다.

### NFS export_location 확인

```bash
# Manila share 목록
openstack share list

# share의 NFS export 경로 확인 (access_to 컬럼)
openstack share show <share-name> -c export_locations
```

출력 예:
```
export_locations: 10.0.0.100:/volumes/_nogroup/share-uuid-xxx
```

이 경로가 `__NFS_EXPORT__` 플레이스홀더 치환값이 된다.

### 빌드 머신에서 Manila share RW 마운트

```bash
# 빌드 머신에서 NFS share 를 RW 마운트 (빌드 머신만 쓰기 필요)
mount -t nfs4 10.0.0.100:/volumes/_nogroup/share-uuid-xxx /srv/layers

# 디렉토리 구조 생성
mkdir -p /srv/layers/images /srv/layers/profiles

# profile 파일 복사
cp layers/profiles/ml-worker.conf /srv/layers/profiles/
```

VM 측에서는 **RO 마운트**한다 (cloud-init fstab 항목 참고).

---

## 2. 레이어 빌드

### 권장: build-layer-diff.sh (OverlayFS diff 방식)

```bash
# 빌드 머신 (root, Ubuntu 24.04)
apt install squashfs-tools

# OUTPUT_DIR = Manila NFS share 마운트 경로
OUTPUT_DIR=/srv/layers/images bash layers/build/build-layer-diff.sh \
    python3 python3 python3-pip python3-venv

# 결과
ls -lh /srv/layers/images/
# python3-20260617120000.sqsh
# python3-latest.sqsh -> python3-20260617120000.sqsh
```

이 방식은 **OverlayFS로 `/`를 감싼 chroot**에서 패키지를 설치하고,
`upper`(= 변경분)만 squashfs로 압축한다. 베이스 OS와 중복되는 파일이 없어 크기가 작다.

### 대안: build-layer.sh (debootstrap 방식)

```bash
OUTPUT_DIR=/srv/layers/images bash layers/build/build-layer.sh \
    python3 python3 python3-pip
```

완전한 Ubuntu 24.04 noble minbase rootfs에서 빌드한다. 빌드 시간이 길지만
호스트 환경에 무관하게 일관된 결과를 낸다.

---

## 3. VM 생성 (cloud-init)

`cloud-init/layer-vm.cloud-config.yaml` 을 복사하고 플레이스홀더를 치환한다:

```bash
sed \
  -e 's|__NFS_EXPORT__|10.0.0.100:/volumes/_nogroup/share-uuid-xxx|g' \
  -e 's|__PROFILE_NAME__|ml-worker|g' \
  layers/cloud-init/layer-vm.cloud-config.yaml \
  > /tmp/my-vm-userdata.yaml

# Nova CLI로 VM 생성
openstack server create \
  --image ubuntu-24.04 \
  --flavor m1.medium \
  --network private \
  --user-data /tmp/my-vm-userdata.yaml \
  my-layer-vm

# 또는 afterglow API (userdata 직접 주입 시)
```

### upper 초기화 옵션

cloud-init의 `runcmd` 주석 참고:
- **옵션 A** (불변): 매 부팅 시 `rm -rf /var/lib/overlay/upper/*` → 레이어 상태만 유지
- **옵션 B** (누적): 아무것도 안 함 → `pip install` 등 사용자 추가 패키지가 upper에 보존됨

---

## 4. VM 내 동작 확인

```bash
# SSH 접속 후
# OverlayFS 마운트 확인
findmnt -t overlay

# 레이어 활성화 로그
journalctl -u layer-activate --no-pager | tail -30

# /usr overlay인 경우 — 레이어의 python 확인
which python3
python3 --version

# 캐시 확인
ls -lh /var/cache/layers/
```

---

## 5. /usr overlay 주의사항

기본 `OVERLAY_TARGET=/usr`로 `/usr` 위에 overlay를 마운트하면:
- `layer-activate.service`가 `Before=multi-user.target`이므로 일반 서비스는 새 `/usr`를 본다.
- 이미 실행 중인 프로세스(cloud-init 자신 등)에는 적용되지 않는다. **재부팅 후 완전 적용**.
- `/usr` remount가 불안한 경우: `OVERLAY_TARGET=/opt/layers/merged` 처럼 전용 경로를 쓰고
  `/etc/profile.d/layer-env.sh`에서 `PATH`/`PYTHONPATH`를 추가한다.

---

## 6. 재부팅 영속화

cloud-init이 설치하는 `/etc/systemd/system/layer-activate.service`가
매 부팅 시 동일 순서로 레이어를 재활성화한다:

```
network-online.target
    ↓
mnt-nfs-layers.mount  (x-systemd.automount via /etc/fstab)
    ↓
layer-activate.service  (Before=multi-user.target)
    ↓
multi-user.target (일반 서비스들)
```

NFS 장애 시 `/var/cache/layers/`에 캐시된 `.sqsh`가 있으면 오프라인에서도 동작한다.

---

## 기존 union.md 방식과의 차이

| 항목 | union.md (CephFS content-addressable) | 이 파이프라인 (squashfs + NFS) |
|------|--------------------------------------|-------------------------------|
| 저장소 | Manila CephFS share (content hash) | Manila NFS share (squashfs 파일) |
| 레이어 포맷 | 파일 트리 (RO, CephFS) | squashfs 이미지 (.sqsh) |
| 소비 방법 | CephFS mount → overlayfs lowerdir | squashfs loop mount → overlayfs |
| 빌드 도구 | Builder VM + recipe_blocks.py | build-uv-python-layer.sh (uv + mksquashfs) |
| 백엔드 연동 | FastAPI API (POST /api/instances) | **`/admin/libraries` 버튼** (POST /api/v1/admin/libraries/build·consume) |
| 커널 캐시 | page cache (CephFS) | page cache (squashfs — NFS보다 효율적) |

squashfs 방식은 NFS round-trip을 최소화하고(커널 page cache 적극 활용),
Manila API·cloud-init 간 복잡한 연동 없이 운영할 수 있다.

관리자 버튼·모니터링 API 상세는 [docs/squashfs-layer-pipeline.md](../docs/squashfs-layer-pipeline.md) 참조.
