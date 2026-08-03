---
title: Palimpsest 로컬 빌드 런북
parent: Palimpsest
nav_order: 10
---

# Palimpsest 로컬 빌드 런북

**로컬 KVM 에서 레이어를 만들어 허브에 올리는** 절차. 사용자 머신에서 진행하며 afterglow
백엔드는 사용자 머신에 접근하지 않는다 — 오가는 것은 HTTP 뿐이다.

```
허브에서 베이스 cloud image 받기  →  로컬 KVM 으로 부팅  →  원하는 걸 설치
   →  변경분을 squashfs 로 패킹  →  허브에 업로드
```

> ⚠️ **이 경로는 CI 로 검증할 수 없다.** 도메인 XML 생성·인자 조립·경로 쿼팅은 단위 테스트
> (`test_palimpsest_kvm.py`, `test_palimpsest_cli.py`)가 덮지만, 실제 부팅·마운트는 사람이 확인한다.
> 도메인 정의와 용어는 [`palimpsest.md`](palimpsest.md) 참조.

## 0. 준비

```bash
sudo apt-get install -y \
  qemu-kvm libvirt-daemon-system libvirt-clients \
  cloud-image-utils squashfs-tools

export PALIMPSEST_URL=https://cloud.example.com
export PALIMPSEST_TOKEN=<access token>
```

CLI 는 `scripts/palimpsest.py` 하나이고 **표준 라이브러리만 쓴다** — 별도 설치가 필요 없다.

```bash
curl -sSLO https://<afterglow>/static/palimpsest.py && chmod +x palimpsest.py
# 또는 저장소에서: scripts/palimpsest.py
```

## 1. 베이스 이미지 받기

```bash
./palimpsest.py images
# sha256:9f2c…  ubuntu-2404   ubuntu-24.04   x86_64   qcow2   612.4 MiB

./palimpsest.py pull sha256:9f2c… -o base.qcow2
# base.qcow2 (612.4 MiB) — digest 검증 완료
```

`pull` 은 받은 뒤 sha256 을 **재계산해 검증**하고, 불일치면 파일을 지운다.

## 2. 빌드용 VM 띄우기

원본은 건드리지 않고 오버레이 위에서 작업한다.

```bash
qemu-img create -F qcow2 -b "$PWD/base.qcow2" -f qcow2 build.qcow2 20G

cat > meta-data <<'EOF'
instance-id: palimpsest-build
local-hostname: palimpsest-build
EOF
cat > user-data <<'EOF'
#cloud-config
ssh_authorized_keys:
  - ssh-ed25519 AAAA... you@host
EOF
cloud-localds seed.iso user-data meta-data

virt-install --name palimpsest-build --memory 4096 --vcpus 2 \
  --disk build.qcow2,bus=virtio --disk seed.iso,device=cdrom \
  --os-variant ubuntu24.04 --import --graphics none --noautoconsole
```

## 3. 레이어로 만들 변경분 뽑기

게스트 안에서 **overlay 로 작업하면 변경분이 그대로 분리**된다. 백엔드 빌드 경로
(`recipe_blocks.squashfs_stacked_layer`)와 같은 방식이다.

```bash
# 게스트 안에서
sudo mkdir -p /mnt/cap/{upper,work,merged}
sudo mount -t overlay overlay \
  -o lowerdir=/,upperdir=/mnt/cap/upper,workdir=/mnt/cap/work /mnt/cap/merged

sudo chroot /mnt/cap/merged /bin/bash -c 'apt-get update && apt-get install -y <원하는 것>'
sudo umount /mnt/cap/merged

# 휘발성 경로는 레이어에 넣지 않는다 (재현성·크기)
sudo rm -rf /mnt/cap/upper/{tmp,run,var/cache,var/lib/apt/lists,var/log,root} \
            /mnt/cap/upper/etc/machine-id
```

`/mnt/cap/upper` 를 호스트로 가져온다(`virt-copy-out`, `scp`, 공유 디렉터리 등).

## 4. 패킹과 업로드

```bash
./palimpsest.py pack ./upper -o mylayer.sqsh
# mylayer.sqsh (184.2 MiB)
# sha256:7ab1…

./palimpsest.py push mylayer.sqsh \
  --name mylayer \
  --base-image sha256:9f2c…            # 어떤 베이스 위에서 만들었는지
  --parent sha256:<부모 레이어>          # 기존 레이어 위에 쌓았다면
# 등록 완료: sha256:7ab1…
```

- digest 를 먼저 선언하므로 **이미 허브에 있는 콘텐츠는 업로드 자체가 생략**된다.
- 서버는 받은 바이트로 digest 를 재계산해 검증한다. 거짓 digest 는 통과하지 못한다.
- `--publish` 를 주면 사이트 전체에 공개된다(기본은 본인 프로젝트만).

베이스 이미지를 직접 올릴 수도 있다:

```bash
./palimpsest.py push ubuntu-24.04.qcow2 --name ubuntu-2404 --kind cloud-image \
  --disk-format qcow2 --arch x86_64 --os-variant ubuntu24.04 --ubuntu-base ubuntu-24.04
```

## 5. 확인

```bash
./palimpsest.py layers --name mylayer
# sha256:7ab1…  mylayer   squashfs   parent=sha256:…

# 스택 전체 + 베이스 이미지를 한 번에 받기
./palimpsest.py bundle sha256:7ab1… -o stack.tar --include-base-image
```

번들은 **OCI image-layout** 이라 그대로 펼치면 곧 레이어 경로가 된다:

```bash
mkdir -p /var/lib/palimpsest/layers && tar -xf stack.tar -C /var/lib/palimpsest/layers
ls /var/lib/palimpsest/layers/blobs/sha256/
```

---

## 부록 A. 플랫폼이 관리하는 KVM 호스트

운영자가 KVM 호스트를 플랫폼에 등록해 두면 백엔드가 직접 도메인을 정의할 수도 있다
(`services/palimpsest_kvm.py`). 이때 레이어는 **virtio-blk 읽기 전용 디스크**로 붙고
게스트는 OpenStack 경로와 동일하게 OverlayFS 로 합성한다.

```toml
[palimpsest]
kvm_uri        = "qemu+ssh://ops@kvm-host/system"
kvm_layer_root = "/var/lib/palimpsest/layers"
kvm_state_dir  = "/var/lib/palimpsest/domains"
```

`libvirt-python` 은 별도 extra 다 — `uv sync --extra kvm`. 설치하지 않으면 이 기능만 503 이다.

게스트 검증:

```bash
lsblk                              # 루트(vda) + 레이어 N개
ls -l /dev/disk/by-id/virtio-*     # ⚠️ /dev/vdb 같은 이름에 의존하면 안 된다
mount | grep squashfs
mount | grep overlay
findmnt -no SOURCE /opt/layers/upper   # 네트워크 FS 가 아니어야 한다
/opt/layers/merged/usr/local/bin/python3 --version
```

## 부록 B. 흔한 실패

| 증상 | 원인 |
|---|---|
| `pull` 후 "digest 불일치" | 전송 중 손상이거나 허브 blob 이 오염됐다. 파일은 자동 삭제된다 |
| `push` 가 413 | `[palimpsest] hub_max_blob_bytes`(기본 32 GiB) 초과 |
| `push` 가 503 | 허브 미설정(`hub_local_path`). 관리자에게 문의 |
| `pack` 이 "mksquashfs 없음" | `squashfs-tools` 미설치 |
| `/dev/disk/by-id/virtio-*` 없음 | serial 이 20자를 넘었다. QEMU 가 자르므로 호스트에서 미리 20자로 만들어야 한다 |
| overlay 마운트 실패 | `upperdir`/`workdir` 가 같은 FS 가 아니거나 네트워크 FS 위에 있다 |
| 레이어 순서가 뒤바뀜 | `lowerdir` 는 **왼쪽이 최상위**다. 루트→리프 입력을 뒤집어야 한다 |
| 26개 넘는 레이어 | virtio-blk 디스크 문자 한도(`vdb`~`vdz`). 병합하거나 EROFS 단일 디바이스 검토 |

## 부록 C. 왜 virtio-blk 인가

`virtiofs` 대신 virtio-blk 을 고른 이유:

- 게스트 스크립트가 OpenStack 경로(NFS → loop-mount → overlay)와 **거의 같다**. 마운트 소스만 다르다.
- `virtiofsd` 데몬을 따로 운영하지 않아도 된다.
- overlayfs `lowerdir` 로서 virtiofs 의 동작은 커널·버전 의존적이다.

대가는 레이어 수만큼 디스크가 늘어난다는 것이다. 레이어가 많아지면 EROFS 의 다중 blob 병합
(여러 레이어를 하나의 파일시스템으로 합쳐 virtio-blk 디바이스 **1개**로 넘김)을 검토할 가치가 있다.
