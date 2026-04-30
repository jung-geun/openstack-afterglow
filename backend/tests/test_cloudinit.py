"""cloudinit.generate_userdata() 헬스체크 주입 테스트."""

import base64

from app.services.cloudinit import generate_userdata

_COMMON_ARGS = dict(
    libraries=[],
    strategy="prebuilt",
    file_storages=[],
    upper_device="/dev/vdb",
    ceph_monitors="192.168.1.1:6789",
    gpu_available=False,
)


def _decode_userdata(encoded: str) -> str:
    return base64.b64decode(encoded).decode()


def test_userdata_without_health_check():
    """report_url 없으면 헬스체크 섹션 미포함."""
    encoded = generate_userdata(**_COMMON_ARGS)
    yaml_str = _decode_userdata(encoded)
    assert "union-health.timer" not in yaml_str
    assert "health-check.sh" not in yaml_str


def test_userdata_with_health_check():
    """report_url+instance_id+report_token 지정 시 헬스체크 섹션 포함."""
    encoded = generate_userdata(
        **_COMMON_ARGS,
        instance_id="test-inst-uuid",
        report_url="https://backend.example.com",
        report_token="test-token-abc",
    )
    yaml_str = _decode_userdata(encoded)
    assert "union-health.timer" in yaml_str
    assert "health-check.sh" in yaml_str
    assert "systemctl enable --now union-health.timer" in yaml_str


def test_health_check_script_contains_url_and_token():
    """health_check.sh.j2 에 report_url / instance_id / report_token이 치환됐는지."""
    encoded = generate_userdata(
        **_COMMON_ARGS,
        instance_id="my-instance-uuid",
        report_url="https://api.example.com",
        report_token="secret-report-token",
    )
    yaml_str = _decode_userdata(encoded)
    assert "https://api.example.com" in yaml_str
    assert "my-instance-uuid" in yaml_str
    assert "secret-report-token" in yaml_str


def test_health_check_includes_file_storages():
    """file_storages가 있을 때 헬스체크 스크립트에 share 이름 포함."""
    fs = [
        {"name": "torch", "share_proto": "NFS", "nfs_export_location": "10.0.0.1:/vol", "mount_options": ""},
    ]
    encoded = generate_userdata(
        libraries=[],
        strategy="prebuilt",
        file_storages=fs,
        upper_device="/dev/vdb",
        ceph_monitors="",
        gpu_available=False,
        instance_id="inst-uuid",
        report_url="https://backend.example.com",
        report_token="tok",
    )
    yaml_str = _decode_userdata(encoded)
    assert "lower_torch" in yaml_str


def test_userdata_partial_health_params_excluded():
    """report_url만 있고 token 없으면 헬스체크 미포함."""
    encoded = generate_userdata(
        **_COMMON_ARGS,
        instance_id="some-id",
        report_url="https://backend.example.com",
        report_token="",  # 빈 토큰 → 미포함
    )
    yaml_str = _decode_userdata(encoded)
    assert "union-health.timer" not in yaml_str


def test_nfs_mount_options_include_security_flags():
    """NFS 마운트 옵션에 nosuid,nodev,noexec 포함되어야 한다."""
    fs = [
        {
            "name": "python311",
            "share_proto": "NFS",
            "nfs_export_location": "10.0.0.1:/vol",
            "mount_options": "hard,intr,noatime,nosuid,nodev,noexec,_netdev,timeo=10,retrans=3",
            "export_path": "",
            "cephx_id": "",
            "cephx_key": "",
        }
    ]
    encoded = generate_userdata(
        libraries=[],
        strategy="prebuilt",
        file_storages=fs,
        upper_device="/dev/vdb",
        ceph_monitors="",
        gpu_available=False,
    )
    yaml_str = _decode_userdata(encoded)
    assert "nosuid" in yaml_str
    assert "nodev" in yaml_str
    assert "noexec" in yaml_str


def test_union_ro_share_export_injected_to_write_files():
    """union_ro_share_export가 지정되면 write_files에 LAYER_STORE_RO_EXPORT 포함."""
    encoded = generate_userdata(
        **_COMMON_ARGS,
        union_ro_share_export="10.0.0.1:6789:/volumes/_nogroup/abc123",
    )
    yaml_str = _decode_userdata(encoded)
    assert "LAYER_STORE_RO_EXPORT" in yaml_str
    assert "10.0.0.1:6789:/volumes/_nogroup/abc123" in yaml_str


def test_userdata_without_gpu_skips_dcgm():
    """gpu_available=False 인스턴스에는 DCGM Exporter 관련 내용이 없어야 한다."""
    encoded = generate_userdata(**{**_COMMON_ARGS, "gpu_available": False})
    yaml_str = _decode_userdata(encoded)
    assert "dcgm-exporter" not in yaml_str
    assert "install_dcgm_exporter.sh" not in yaml_str


def test_userdata_with_gpu_installs_dcgm():
    """gpu_available=True 인스턴스에는 DCGM Exporter 설치 스크립트와 systemd unit이 포함돼야 한다."""
    encoded = generate_userdata(**{**_COMMON_ARGS, "gpu_available": True})
    yaml_str = _decode_userdata(encoded)
    assert "/usr/local/bin/dcgm-exporter" in yaml_str
    assert "0.0.0.0:9400" in yaml_str
    assert "systemctl enable --now dcgm-exporter.service" in yaml_str
    assert "github.com/NVIDIA/dcgm-exporter/releases" in yaml_str


def test_userdata_with_gpu_uses_pinned_version():
    """생성된 cloud-init에 모듈 상수 버전이 포함돼야 한다."""
    from app.services import cloudinit as ci

    encoded = generate_userdata(**{**_COMMON_ARGS, "gpu_available": True})
    yaml_str = _decode_userdata(encoded)
    assert ci._DCGM_EXPORTER_VERSION in yaml_str


def test_rotate_key_script_not_injected_when_disabled():
    """union_cephx_rotate_hours=0 이면 rotate-key 스크립트 미포함."""
    encoded = generate_userdata(**{**_COMMON_ARGS, "union_cephx_rotate_hours": 0})
    yaml_str = _decode_userdata(encoded)
    assert "envmgr-rotate-key.sh" not in yaml_str
    assert "union-rotate-key.service" not in yaml_str


def test_rotate_key_script_injected_to_write_files():
    """union_cephx_rotate_hours > 0 이면 /usr/local/bin/envmgr-rotate-key.sh 주입."""
    encoded = generate_userdata(**{**_COMMON_ARGS, "union_cephx_rotate_hours": 24})
    yaml_str = _decode_userdata(encoded)
    assert "path: /usr/local/bin/envmgr-rotate-key.sh" in yaml_str
    assert 'permissions: "0750"' in yaml_str
    assert "CephX 키 회전" in yaml_str


def test_rotate_key_systemd_unit_present_when_enabled():
    """union_cephx_rotate_hours > 0 이면 systemd service/timer 항목도 포함."""
    encoded = generate_userdata(**{**_COMMON_ARGS, "union_cephx_rotate_hours": 24})
    yaml_str = _decode_userdata(encoded)
    assert "union-rotate-key.service" in yaml_str
    assert "union-rotate-key.timer" in yaml_str
    assert "ExecStart=/usr/local/bin/envmgr-rotate-key.sh" in yaml_str


def test_rotate_key_script_before_systemd_unit():
    """write_files에서 rotate-key.sh 주입이 systemd unit 선언보다 먼저 나와야 한다."""
    encoded = generate_userdata(**{**_COMMON_ARGS, "union_cephx_rotate_hours": 24})
    yaml_str = _decode_userdata(encoded)
    script_pos = yaml_str.find("path: /usr/local/bin/envmgr-rotate-key.sh")
    service_pos = yaml_str.find("path: /etc/systemd/system/union-rotate-key.service")
    assert script_pos < service_pos, "rotate-key.sh write_files 항목이 service 선언보다 앞서야 함"
