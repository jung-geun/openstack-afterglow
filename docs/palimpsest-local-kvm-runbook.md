---
title: Palimpsest 로컬 KVM 런북
parent: Palimpsest
nav_order: 10
---

# Palimpsest 로컬 KVM 런북

OpenStack 없이 로컬(또는 원격) KVM 호스트에 레이어드 VM 을 띄우는 수동 절차.

> ⚠️ **이 경로는 CI 로 검증할 수 없다.** `backend/tests/test_palimpsest_kvm.py` 는 도메인 XML 생성 ·
> seed ISO 인자 조립 · 경로 쿼팅까지만 덮는다. 실제 부팅·마운트·라우팅은 아래 절차로 사람이 확인한다.
> 도메인 정의와 용어는 [`palimpsest.md`](palimpsest.md) 참조.

## 0. 전제

호스트에 필요한 것:

```bash
sudo apt-get install -y \
  qemu-kvm libvirt-daemon-system libvirt-clients \
  cloud-image-utils   # cloud-localds
```

백엔드 쪽:

```bash
cd backend && uv sync --extra kvm    # libvirt-python (시스템 libvirt-dev 필요)
```

`afterglow.conf`:

```toml
[palimpsest]
kvm_uri        = "qemu:///system"                  # 원격이면 "qemu+ssh://ops@kvm-host/system"
kvm_layer_root = "/var/lib/palimpsest/layers"
kvm_state_dir  = "/var/lib/palimpsest/domains"
```

`kvm_uri` 가 비어 있으면 기능은 비활성이고 관련 호출은 503 이다.

## 1. 레이어를 호스트에 펼치기

허브 번들은 **OCI image-layout** 이라 그대로 풀면 곧바로 레이어 경로가 된다.

```bash
# 리프 레이어 digest 하나만 주면 부모 체인 전체가 담겨 온다
curl -sS -X POST https://<afterglow>/api/v1/palimpsest/hub/bundles \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"refs":["sha256:<leaf-digest>"]}' \
  -o bundle.tar

sudo mkdir -p /var/lib/palimpsest/layers
sudo tar -xf bundle.tar -C /var/lib/palimpsest/layers
```

확인 — 체인의 모든 레이어가 있어야 한다:

```bash
ls /var/lib/palimpsest/layers/blobs/sha256/ | wc -l
jq -r '.manifests[0].digest' /var/lib/palimpsest/layers/index.json
```

## 2. 루트 오버레이와 seed ISO 준비

```bash
sudo mkdir -p /var/lib/palimpsest/domains
cd /var/lib/palimpsest/domains

# Ubuntu 클라우드 이미지 위에 qcow2 오버레이 — 원본은 건드리지 않는다
sudo qemu-img create -F qcow2 -b /var/lib/libvirt/images/ubuntu-24.04.qcow2 \
  -f qcow2 demo.qcow2 20G

cat > meta-data <<'EOF'
instance-id: palimpsest-demo
local-hostname: palimpsest-demo
EOF

# user-data 는 백엔드가 렌더한 것을 쓴다(레이어 조립 스크립트 포함).
# 수동 확인용 최소본:
cat > user-data <<'EOF'
#cloud-config
packages: [squashfs-tools]
runcmd:
  - [ bash, /var/lib/cloud/instance/scripts/layer-activate.sh ]
EOF

sudo cloud-localds demo-seed.iso user-data meta-data
```

## 3. 도메인 정의·부팅

백엔드의 `palimpsest_kvm.build_domain_xml` 이 만든 XML 을 쓴다. 손으로 확인할 때는:

```bash
virsh define /tmp/palimpsest-demo.xml
virsh start palimpsest-demo
virsh console palimpsest-demo
```

## 4. 검증 (여기가 핵심)

게스트 안에서:

```bash
# ① 레이어 디스크가 전부 보이는가 — 루트(vda) + 레이어 N개
lsblk

# ② by-id 심볼릭 링크가 있는가.
#    ⚠️ /dev/vdb 같은 이름에 의존하면 안 된다 — 부착 순서와 게스트 이름 순서는 보장되지 않는다.
ls -l /dev/disk/by-id/virtio-*

# ③ 각 레이어가 squashfs 로 마운트됐는가
mount | grep squashfs

# ④ overlay 가 합성됐고 upper/work 가 로컬 디스크인가
mount | grep overlay
findmnt -no SOURCE /opt/layers/upper    # 네트워크 FS 가 아니어야 한다

# ⑤ 실제로 쓸 수 있는가 — 레이어가 제공하는 것을 실행
/opt/layers/merged/usr/local/bin/python3 --version
```

**흔한 실패**

| 증상 | 원인 |
|---|---|
| `/dev/disk/by-id/virtio-*` 없음 | serial 이 20자를 넘었다. QEMU 가 자르므로 호스트에서 미리 20자로 만들어야 한다 |
| `mount: unknown filesystem type 'squashfs'` | 게스트에 `squashfs-tools`/커널 모듈 없음 |
| overlay 마운트 실패 | `upperdir`/`workdir` 가 같은 파일시스템이 아니거나 네트워크 FS 위에 있다 |
| 레이어 순서가 뒤바뀜 | `lowerdir` 는 **왼쪽이 최상위**다. 루트→리프 입력을 뒤집어야 한다 |
| 26개 넘는 레이어 | virtio-blk 디스크 문자 한도(`vdb`~`vdz`). 레이어를 병합하거나 EROFS 단일 디바이스 검토 |

## 5. 정리

```bash
virsh destroy palimpsest-demo
virsh undefine palimpsest-demo
sudo rm -f /var/lib/palimpsest/domains/demo.qcow2 /var/lib/palimpsest/domains/demo-seed.iso
```

레이어 blob 은 콘텐츠 주소라 여러 도메인이 공유한다 — 도메인을 지운다고 지우지 않는다.

## 부록. 왜 virtio-blk 인가

`virtiofs` 대신 virtio-blk 을 고른 이유:

- 게스트 스크립트가 OpenStack 경로(NFS → loop-mount → overlay)와 **거의 같다**. 마운트 소스만 다르다.
- `virtiofsd` 데몬을 따로 운영하지 않아도 된다.
- overlayfs `lowerdir` 로서 virtiofs 의 동작은 커널·버전 의존적이다.

대가는 레이어 수만큼 디스크가 늘어난다는 것이다. 레이어가 많아지면 EROFS 의 다중 blob 병합
(여러 레이어를 하나의 파일시스템으로 합쳐 virtio-blk 디바이스 **1개**로 넘김)을 검토할 가치가 있다.
현재 파이프라인은 `mksquashfs` 가 `recipe_blocks.py` 에 박혀 있어 squashfs 를 유지한다.
