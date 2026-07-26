"""Palimpsest 로컬 KVM 런타임 단위 테스트.

⚠️ **실제 부팅은 CI 로 검증할 수 없다.** 여기서 덮는 것은 도메인 XML 생성 · seed ISO 인자 조립 ·
경로 쿼팅까지다. 실환경 확인은 `docs/palimpsest-local-kvm-runbook.md` 의 수동 절차로 한다.

고정하는 계약:
- 레이어 디스크는 **읽기 전용** — 봉인된 불변 레이어를 게스트가 건드리면 안 된다
- 게스트는 `/dev/vdX` 가 아니라 **serial 기반 `/dev/disk/by-id/virtio-<serial>`** 로 찾는다
  (부착 순서와 게스트 디바이스 이름 순서는 보장되지 않는다)
- serial 은 QEMU 가 20자로 자르므로 호스트 쪽에서 미리 20자로 만든다
- lowerdir 는 왼쪽이 최상위이므로 루트→리프 입력을 **뒤집어** 넣는다
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.palimpsest_kvm import (
    MAX_LAYER_DISKS,
    DomainSpec,
    KvmError,
    KvmUnavailable,
    build_domain_xml,
    build_layer_activation_script,
    build_layer_disks,
    build_seed_iso_command,
    connect,
    destroy_and_undefine,
    layer_blob_path,
    run_seed_iso,
)

_ROOT = Path("/var/lib/palimpsest/layers")
_DIGESTS = [f"sha256:{chr(ord('a') + i) * 64}" for i in range(3)]


def _spec(layers=None) -> DomainSpec:
    return DomainSpec(
        name="palimpsest-demo",
        memory_mib=4096,
        vcpus=2,
        root_disk=Path("/var/lib/palimpsest/domains/demo.qcow2"),
        seed_iso=Path("/var/lib/palimpsest/domains/demo-seed.iso"),
        layers=layers if layers is not None else build_layer_disks(_ROOT, _DIGESTS),
    )


# ---------------------------------------------------------------------------
# 레이어 경로 / 디스크 배치
# ---------------------------------------------------------------------------


def test_layer_blob_path_matches_oci_image_layout():
    # 허브 번들을 그대로 펼치면 이 배치가 된다
    path = layer_blob_path(_ROOT, _DIGESTS[0])

    assert path == _ROOT / "blobs" / "sha256" / ("a" * 64)


@pytest.mark.parametrize(
    "bad", ["../../etc/passwd", "sha256:../x", "sha256:zz", "", "sha256:" + "a" * 63, "md5:" + "a" * 32]
)
def test_layer_blob_path_rejects_traversal_and_malformed(bad):
    with pytest.raises(KvmError):
        layer_blob_path(_ROOT, bad)


def test_layer_disks_assign_sequential_virtio_targets():
    disks = build_layer_disks(_ROOT, _DIGESTS)

    assert [d.target_dev for d in disks] == ["vdb", "vdc", "vdd"]
    # vda 는 루트 오버레이 몫이다
    assert all(d.target_dev != "vda" for d in disks)


def test_layer_disk_serial_is_truncated_to_qemu_limit():
    disks = build_layer_disks(_ROOT, _DIGESTS)

    for disk in disks:
        # QEMU 가 serial 을 20자로 자른다 — 게스트의 by-id 경로와 맞추려면 여기서 미리 잘라야 한다
        assert len(disk.serial) == 20
        assert disk.blob_digest.endswith(disk.serial) or disk.blob_digest[7:].startswith(disk.serial)


def test_layer_disks_reject_empty_and_over_limit():
    with pytest.raises(KvmError):
        build_layer_disks(_ROOT, [])

    too_many = [f"sha256:{i:064x}" for i in range(MAX_LAYER_DISKS + 1)]
    with pytest.raises(KvmError, match="한도"):
        build_layer_disks(_ROOT, too_many)


# ---------------------------------------------------------------------------
# 도메인 XML
# ---------------------------------------------------------------------------


def test_domain_xml_marks_every_layer_disk_readonly():
    xml = ET.fromstring(build_domain_xml(_spec()))

    layer_disks = [
        disk
        for disk in xml.findall("./devices/disk")
        if (disk.find("target") is not None and disk.find("target").get("dev", "").startswith("vd"))
        and disk.find("target").get("dev") != "vda"
    ]
    assert len(layer_disks) == 3
    for disk in layer_disks:
        # 봉인된 불변 레이어다 — 게스트가 쓰면 안 된다
        assert disk.find("readonly") is not None, "레이어 디스크가 읽기 전용이 아니다"
        assert disk.find("driver").get("type") == "raw"


def test_domain_xml_root_disk_is_writable_qcow2():
    xml = ET.fromstring(build_domain_xml(_spec()))

    root = next(d for d in xml.findall("./devices/disk") if d.find("target").get("dev") == "vda")

    # overlayfs upper/work 가 여기 올라간다 — 반드시 쓰기 가능해야 한다
    assert root.find("readonly") is None
    assert root.find("driver").get("type") == "qcow2"


def test_domain_xml_carries_serial_for_stable_guest_lookup():
    disks = build_layer_disks(_ROOT, _DIGESTS)
    xml = ET.fromstring(build_domain_xml(_spec(disks)))

    serials = [d.findtext("serial") for d in xml.findall("./devices/disk") if d.findtext("serial")]

    assert serials == [d.serial for d in disks]


def test_domain_xml_attaches_nocloud_seed_as_cdrom():
    xml = ET.fromstring(build_domain_xml(_spec()))

    cdrom = next(d for d in xml.findall("./devices/disk") if d.get("device") == "cdrom")

    assert cdrom.find("source").get("file").endswith("-seed.iso")
    assert cdrom.find("readonly") is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "Bad Name"), ("name", "../evil"), ("memory_mib", 16), ("vcpus", 0), ("vcpus", 9999)],
)
def test_domain_xml_rejects_invalid_spec(field, value):
    spec = _spec()
    bad = DomainSpec(**{**spec.__dict__, field: value})

    with pytest.raises(KvmError):
        build_domain_xml(bad)


# ---------------------------------------------------------------------------
# seed ISO
# ---------------------------------------------------------------------------


def test_seed_iso_command_is_argument_list_not_shell():
    command = build_seed_iso_command(Path("/s/seed.iso"), Path("/s/user-data"), Path("/s/meta-data"))

    # 셸을 거치지 않는다 — 인자 리스트를 그대로 전달한다
    assert command == ["cloud-localds", "/s/seed.iso", "/s/user-data", "/s/meta-data"]
    assert all(isinstance(part, str) for part in command)


def test_seed_iso_command_rejects_empty_paths():
    with pytest.raises(KvmError):
        build_seed_iso_command(Path("/s/seed.iso"), Path(""), Path("/s/meta-data"))


def test_run_seed_iso_reports_missing_tool_actionably():
    with patch("app.services.palimpsest_kvm.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(KvmError, match="cloud-image-utils"):
            run_seed_iso(Path("/s/seed.iso"), Path("/s/user-data"), Path("/s/meta-data"))


def test_run_seed_iso_passes_no_shell():
    with patch("app.services.palimpsest_kvm.subprocess.run") as run:
        run_seed_iso(Path("/s/seed.iso"), Path("/s/user-data"), Path("/s/meta-data"))

    args, kwargs = run.call_args
    assert isinstance(args[0], list)
    assert "shell" not in kwargs or kwargs["shell"] is False


# ---------------------------------------------------------------------------
# 게스트 조립 스크립트
# ---------------------------------------------------------------------------


def test_activation_script_uses_by_id_not_device_names():
    disks = build_layer_disks(_ROOT, _DIGESTS)

    script = build_layer_activation_script(disks)

    # 부착 순서와 게스트 디바이스 이름 순서는 보장되지 않는다 — by-id 가 유일한 근거다
    assert "/dev/vdb" not in script
    for disk in disks:
        assert f"/dev/disk/by-id/virtio-{disk.serial}" in script


def test_activation_script_reverses_chain_for_lowerdir():
    disks = build_layer_disks(_ROOT, _DIGESTS)

    script = build_layer_activation_script(disks)
    lowerdir = next(line for line in script.splitlines() if "lowerdir=" in line)

    # 입력은 루트→리프. lowerdir 는 왼쪽이 최상위이므로 리프가 먼저 와야 한다.
    assert lowerdir.index("lower2") < lowerdir.index("lower1") < lowerdir.index("lower0")


def test_activation_script_keeps_upper_and_work_on_local_disk():
    script = build_layer_activation_script(build_layer_disks(_ROOT, _DIGESTS))

    # upper/work 를 네트워크 파일시스템에 두면 overlayfs 가 조용히 깨진다 (docs/palimpsest.md §5)
    assert "upperdir=/opt/layers/upper" in script
    assert "workdir=/opt/layers/work" in script


def test_activation_script_mounts_layers_read_only_and_waits_for_udev():
    script = build_layer_activation_script(build_layer_disks(_ROOT, _DIGESTS))

    assert script.count("mount -t squashfs -o ro") == 3
    # udev 가 by-id 심볼릭 링크를 만들기 전에 마운트하면 실패한다
    assert "seq 1 30" in script
    assert script.startswith("set -euo pipefail")


def test_activation_script_quotes_merged_dir():
    script = build_layer_activation_script(build_layer_disks(_ROOT, _DIGESTS), merged_dir="/opt/layers/my merged")

    assert "'/opt/layers/my merged'" in script


# ---------------------------------------------------------------------------
# libvirt 연결 (지연 import)
# ---------------------------------------------------------------------------


def test_connect_is_unavailable_without_uri():
    with pytest.raises(KvmUnavailable, match="kvm_uri"):
        connect("")


def test_connect_reports_missing_libvirt_actionably():
    with patch("app.services.palimpsest_kvm._libvirt", side_effect=KvmUnavailable("libvirt-python 미설치")):
        with pytest.raises(KvmUnavailable):
            connect("qemu:///system")


def test_destroy_and_undefine_is_best_effort_when_domain_absent():
    fake_libvirt = MagicMock()
    fake_libvirt.libvirtError = RuntimeError
    conn = MagicMock()
    conn.lookupByName.side_effect = RuntimeError("no domain")

    with patch("app.services.palimpsest_kvm._libvirt", return_value=fake_libvirt):
        destroy_and_undefine(conn, "palimpsest-demo")  # 예외를 던지지 않아야 한다

    conn.lookupByName.assert_called_once_with("palimpsest-demo")


def test_module_generates_xml_without_parsing_untrusted_input():
    # XXE 표면이 없음을 고정한다 — 이 모듈은 XML 을 생성만 한다.
    source = Path(__file__).parent.parent / "app" / "services" / "palimpsest_kvm.py"
    text = source.read_text(encoding="utf-8")

    assert "fromstring" not in text
    assert "ET.parse" not in text
