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
