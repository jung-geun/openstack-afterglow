"""Palimpsest 로컬 KVM 런타임 — libvirt + NoCloud + virtio-blk.

OpenStack 없이 로컬(또는 원격) KVM 호스트에 레이어드 VM 을 띄운다. 레이어는 호스트 경로에
쌓여 있고 **virtio-blk 읽기 전용 디스크**로 붙는다. 게스트는 OpenStack 경로와 똑같이
`mount -t squashfs` → OverlayFS 합성을 한다.

호스트 레이어 경로 규약 — 허브 OCI 번들을 그대로 펼치면 이 배치가 된다:

    <layer_root>/blobs/sha256/<hex>

virtio-blk 을 고르는 이유(docs/palimpsest.md §4): 게스트 스크립트가 OpenStack 경로
(loop-mount → overlay)와 거의 같아 재사용률이 높다. virtiofs 는 `virtiofsd` 데몬 운영이
추가되고 overlayfs `lowerdir` 로서의 동작이 커널·버전 의존적이다.

**libvirt 는 지연 import** 한다 — `libvirt-python` 은 시스템 라이브러리를 요구하므로 기본
배포 이미지에 없다. 없으면 이 기능만 비활성(503)이고 나머지는 영향이 없다.

⚠️ **이 모듈은 CI 로 검증할 수 없다.** 단위 테스트는 도메인 XML 생성·seed ISO 인자 조립·
경로 쿼팅까지만 덮고, 실제 부팅은 `docs/palimpsest-local-kvm-runbook.md` 의 수동 절차로 확인한다.
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess

# 이 모듈은 XML 을 **생성만** 한다(Element/SubElement/tostring). 파싱 경로가 없으므로
# XXE·billion-laughs 표면이 없다 — defusedxml 이 필요하지 않다.
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from app.services.palimpsest_digest import normalize_digest

_logger = logging.getLogger(__name__)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_DOMAIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
# virtio-blk 디스크 이름: vda(부트) + vdb.. (레이어). 알파벳 하나로 최대 25개 레이어.
_DISK_LETTERS = "bcdefghijklmnopqrstuvwxyz"
MAX_LAYER_DISKS = len(_DISK_LETTERS)


class KvmError(RuntimeError):
    """로컬 KVM 런타임 오류."""


class KvmUnavailable(KvmError):
    """libvirt 를 쓸 수 없다 — 미설치이거나 `[palimpsest] kvm_uri` 미설정."""


@dataclass(frozen=True)
class LayerDisk:
    """게스트에 붙일 레이어 디스크 하나."""

    blob_digest: str
    host_path: Path
    target_dev: str  # vdb, vdc, ...
    serial: str  # 게스트가 /dev/disk/by-id 로 찾을 때 쓰는 안정 식별자


@dataclass(frozen=True)
class DomainSpec:
    name: str
    memory_mib: int
    vcpus: int
    root_disk: Path  # qcow2 오버레이 (쓰기 가능)
    seed_iso: Path  # NoCloud cidata
    layers: list[LayerDisk]
    network: str = "default"


def layer_blob_path(layer_root: Path, digest: str) -> Path:
    """허브 OCI image-layout 과 같은 배치 — `<root>/blobs/sha256/<hex>`.

    digest 는 경로 조립에 쓰이므로 형식을 강제한다(traversal 방어).
    """
    normalized = normalize_digest(digest)
    if normalized is None:
        raise KvmError(f"digest 형식이 유효하지 않습니다: {digest!r}")
    hex_part = normalized[len("sha256:") :]
    if not _HEX64_RE.match(hex_part):
        raise KvmError("digest hex 검증 실패")
    return layer_root / "blobs" / "sha256" / hex_part


def build_layer_disks(layer_root: Path, digests: list[str]) -> list[LayerDisk]:
    """루트→리프 순서의 digest 목록을 virtio-blk 디스크 배치로 바꾼다.

    serial 은 digest 앞 20자다 — QEMU 가 serial 을 20자로 자르므로 게스트의
    `/dev/disk/by-id/virtio-<serial>` 과 정확히 맞추기 위해 여기서 미리 자른다.
    """
    if not digests:
        raise KvmError("레이어가 하나도 없습니다")
    if len(digests) > MAX_LAYER_DISKS:
        raise KvmError(
            f"레이어 수({len(digests)})가 virtio-blk 디스크 한도({MAX_LAYER_DISKS})를 넘습니다 "
            "— 레이어를 병합하거나 EROFS 단일 디바이스 방식을 검토하세요"
        )
    disks: list[LayerDisk] = []
    for index, digest in enumerate(digests):
        path = layer_blob_path(layer_root, digest)
        normalized = normalize_digest(digest)
        assert normalized is not None  # layer_blob_path 가 이미 검증했다
        disks.append(
            LayerDisk(
                blob_digest=normalized,
                host_path=path,
                target_dev=f"vd{_DISK_LETTERS[index]}",
                serial=normalized[len("sha256:") :][:20],
            )
        )
    return disks


def build_domain_xml(spec: DomainSpec) -> str:
    """libvirt 도메인 XML 을 만든다.

    레이어 디스크는 전부 `readonly` 다 — 봉인된 불변 레이어를 게스트가 건드리면 안 된다.
    """
    if not _DOMAIN_NAME_RE.match(spec.name):
        raise KvmError("도메인 이름은 소문자/숫자/하이픈만 허용하며 63자 이하여야 합니다")
    if spec.memory_mib < 256 or spec.memory_mib > 1024 * 1024:
        raise KvmError("memory_mib 범위를 벗어났습니다")
    if spec.vcpus < 1 or spec.vcpus > 256:
        raise KvmError("vcpus 범위를 벗어났습니다")

    domain = ET.Element("domain", {"type": "kvm"})
    ET.SubElement(domain, "name").text = spec.name
    ET.SubElement(domain, "memory", {"unit": "MiB"}).text = str(spec.memory_mib)
    ET.SubElement(domain, "vcpu").text = str(spec.vcpus)

    os_el = ET.SubElement(domain, "os")
    ET.SubElement(os_el, "type", {"arch": "x86_64", "machine": "q35"}).text = "hvm"
    ET.SubElement(os_el, "boot", {"dev": "hd"})

    features = ET.SubElement(domain, "features")
    ET.SubElement(features, "acpi")
    ET.SubElement(features, "apic")

    ET.SubElement(domain, "cpu", {"mode": "host-passthrough"})
    devices = ET.SubElement(domain, "devices")
    ET.SubElement(devices, "emulator").text = "/usr/bin/qemu-system-x86_64"

    # 루트 디스크 (qcow2 오버레이 — 쓰기 가능). overlayfs upper 는 여기 올라간다.
    root = ET.SubElement(devices, "disk", {"type": "file", "device": "disk"})
    ET.SubElement(root, "driver", {"name": "qemu", "type": "qcow2", "discard": "unmap"})
    ET.SubElement(root, "source", {"file": str(spec.root_disk)})
    ET.SubElement(root, "target", {"dev": "vda", "bus": "virtio"})

    # 레이어 디스크 (raw squashfs, 읽기 전용)
    for layer in spec.layers:
        disk = ET.SubElement(devices, "disk", {"type": "file", "device": "disk"})
        ET.SubElement(disk, "driver", {"name": "qemu", "type": "raw"})
        ET.SubElement(disk, "source", {"file": str(layer.host_path)})
        ET.SubElement(disk, "target", {"dev": layer.target_dev, "bus": "virtio"})
        # 게스트가 /dev/disk/by-id/virtio-<serial> 로 안정적으로 찾는다.
        # 부착 순서와 게스트 디바이스 이름 순서는 보장되지 않으므로 serial 이 유일한 근거다.
        ET.SubElement(disk, "serial").text = layer.serial
        ET.SubElement(disk, "readonly")

    # NoCloud seed (cidata 라벨을 단 ISO)
    seed = ET.SubElement(devices, "disk", {"type": "file", "device": "cdrom"})
    ET.SubElement(seed, "driver", {"name": "qemu", "type": "raw"})
    ET.SubElement(seed, "source", {"file": str(spec.seed_iso)})
    ET.SubElement(seed, "target", {"dev": "sda", "bus": "sata"})
    ET.SubElement(seed, "readonly")

    interface = ET.SubElement(devices, "interface", {"type": "network"})
    ET.SubElement(interface, "source", {"network": spec.network})
    ET.SubElement(interface, "model", {"type": "virtio"})

    console = ET.SubElement(devices, "console", {"type": "pty"})
    ET.SubElement(console, "target", {"type": "serial", "port": "0"})
    ET.SubElement(devices, "channel", {"type": "unix"}).append(
        ET.Element("target", {"type": "virtio", "name": "org.qemu.guest_agent.0"})
    )

    return ET.tostring(domain, encoding="unicode")


def build_seed_iso_command(seed_iso: Path, user_data: Path, meta_data: Path) -> list[str]:
    """`cloud-localds` 호출 인자. 셸을 거치지 않도록 리스트로 만든다.

    NoCloud 데이터소스는 `cidata` 라벨을 단 디스크를 찾는다 — cloud-localds 가 그 라벨을 붙인다.
    """
    # 호스트 경로이므로 절대 경로만 받는다. `Path("")` 는 `.` 로 정규화되어 빈 문자열 검사를
    # 빠져나가므로 is_absolute() 로 확인해야 한다.
    for label, path in (("seed_iso", seed_iso), ("user_data", user_data), ("meta_data", meta_data)):
        if not path.is_absolute():
            raise KvmError(f"{label} 는 절대 경로여야 합니다: {str(path)!r}")
    return ["cloud-localds", str(seed_iso), str(user_data), str(meta_data)]


def build_layer_activation_script(disks: list[LayerDisk], *, merged_dir: str = "/opt/layers/merged") -> str:
    """게스트에서 실행할 레이어 조립 스크립트.

    **디스크 이름(`/dev/vdb`)에 의존하지 않는다** — 부착 순서와 게스트 디바이스 이름 순서는
    보장되지 않는다. QEMU serial 로 만들어지는 `/dev/disk/by-id/virtio-<serial>` 을 쓴다.

    lowerdir 는 왼쪽이 최상위이므로 루트→리프 순서를 **뒤집어** 넣는다(docs/palimpsest.md §5).
    upper/work 는 반드시 VM 로컬 디스크에 둔다.
    """
    lines = [
        "set -euo pipefail",
        "mkdir -p /opt/layers/upper /opt/layers/work " + shlex.quote(merged_dir),
    ]
    lower_dirs: list[str] = []
    for index, layer in enumerate(disks):
        mount_point = f"/mnt/palimpsest/lower{index}"
        by_id = f"/dev/disk/by-id/virtio-{layer.serial}"
        lines += [
            f"mkdir -p {shlex.quote(mount_point)}",
            f"DEV={shlex.quote(by_id)}",
            # 커널이 by-id 심볼릭 링크를 만들 때까지 잠깐 기다린다(udev 경합).
            'for _ in $(seq 1 30); do [ -e "$DEV" ] && break; sleep 1; done',
            '[ -e "$DEV" ] || { echo "레이어 디스크 미발견: $DEV" >&2; exit 1; }',
            f'mount -t squashfs -o ro "$DEV" {shlex.quote(mount_point)}',
        ]
        lower_dirs.append(mount_point)

    # 루트→리프로 받았으므로 뒤집어야 리프가 최상위가 된다.
    lowerdir = ":".join(shlex.quote(path) for path in reversed(lower_dirs))
    lines.append(
        "mount -t overlay overlay -o "
        f"lowerdir={lowerdir},upperdir=/opt/layers/upper,workdir=/opt/layers/work "
        f"{shlex.quote(merged_dir)}"
    )
    return "\n".join(lines) + "\n"


def run_seed_iso(seed_iso: Path, user_data: Path, meta_data: Path) -> None:
    """seed ISO 를 굽는다. 셸을 쓰지 않는다(인자 리스트 직접 전달)."""
    command = build_seed_iso_command(seed_iso, user_data, meta_data)
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)  # noqa: S603
    except FileNotFoundError as exc:
        raise KvmError("cloud-localds 를 찾을 수 없습니다 (cloud-image-utils 패키지 필요)") from exc
    except subprocess.CalledProcessError as exc:
        raise KvmError(f"seed ISO 생성 실패: {exc.stderr.decode(errors='replace')[:200]}") from exc


def _libvirt():
    """libvirt 를 지연 import 한다 — 미설치 배포에서 모듈 로드를 막지 않기 위해."""
    try:
        import libvirt  # noqa: PLC0415 — 지연 import 가 의도다
    except ImportError as exc:  # pragma: no cover - 설치 환경에 따라 다름
        raise KvmUnavailable(
            "libvirt-python 이 설치되지 않았습니다 — `uv sync --extra kvm` 후 다시 시도하세요"
        ) from exc
    return libvirt


def connect(uri: str):
    """libvirt 연결을 연다. `qemu:///system` 또는 `qemu+ssh://user@host/system`."""
    if not uri.strip():
        raise KvmUnavailable("[palimpsest] kvm_uri 가 설정되지 않았습니다 — 로컬 KVM 기능이 비활성입니다")
    libvirt = _libvirt()
    conn = libvirt.open(uri)
    if conn is None:  # pragma: no cover - libvirt 가 보통은 예외를 던진다
        raise KvmError(f"libvirt 연결에 실패했습니다: {uri}")
    return conn


def define_and_start(conn, name: str, domain_xml: str):
    """도메인을 정의하고 시작한다. 이미 같은 이름이 있으면 거부한다.

    이름을 XML 에서 파싱하지 않고 인자로 받는다 — XML 파서를 쓰지 않으면 XXE 같은 표면이
    아예 생기지 않고, 호출자는 어차피 `DomainSpec.name` 을 들고 있다.
    """
    if not _DOMAIN_NAME_RE.match(name):
        raise KvmError("도메인 이름 형식이 유효하지 않습니다")
    libvirt = _libvirt()
    try:
        existing = conn.lookupByName(name)
    except libvirt.libvirtError:
        existing = None
    if existing is not None:
        raise KvmError(f"같은 이름의 도메인이 이미 있습니다: {name}")
    domain = conn.defineXML(domain_xml)
    if domain is None:  # pragma: no cover
        raise KvmError("도메인 정의에 실패했습니다")
    domain.create()
    return domain


def destroy_and_undefine(conn, name: str) -> None:
    """도메인을 정지하고 정의를 지운다. 각 단계는 best-effort."""
    libvirt = _libvirt()
    try:
        domain = conn.lookupByName(name)
    except libvirt.libvirtError:
        return
    try:
        if domain.isActive():
            domain.destroy()
    except libvirt.libvirtError:
        _logger.warning("[palimpsest_kvm] 도메인 정지 실패: %s", name, exc_info=True)
    try:
        domain.undefine()
    except libvirt.libvirtError:
        _logger.warning("[palimpsest_kvm] 도메인 정의 삭제 실패: %s", name, exc_info=True)
