"""PR3 회귀 테스트 — Barbican KMS plugin 외부 systemd service 패턴.

이전 host static pod 패턴(§ 7f1de4c)이 K3s 1.34 의 kubelet startup sequence 와
양립 불가하여 cluster 영구 데드락 발생. 본 테스트는 새 systemd service 패턴이
다음을 보장하는지 검증:
- static pod manifest 가 더 이상 작성되지 않음
- systemd unit 파일 + install script + cloud.conf + encryption-config 4개 파일 작성
- k3s server install args 에서 pod-manifest-path 제거 (encryption-provider-config 만 유지)
- cloud-init runcmd 가 KMS install → start → sock wait → k3s start 순서를 보장
"""

from unittest.mock import MagicMock

from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin


def _settings_with_kms() -> MagicMock:
    s = MagicMock()
    s.k3s_barbican_kms_enabled = True
    s.k3s_barbican_kms_kek_id = "kek-uuid-test"
    s.k3s_barbican_kms_image = "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1"
    s.os_auth_url = "https://keystone.example.com:5000/v3"
    s.os_username = "admin"
    s.os_password = "secret"
    s.os_user_domain_name = "Default"
    s.os_project_name = "admin"
    s.os_project_domain_name = "Default"
    s.os_region_name = "RegionOne"
    s.os_insecure = True
    s.os_cacert = ""
    return s


# ---------------------------------------------------------------------------
# extra_write_files — 4개 파일 (systemd unit + install script + cloud.conf + enc-config)
# ---------------------------------------------------------------------------


def test_extra_write_files_does_not_include_static_pod_manifest():
    """PR3 핵심: host static pod manifest 가 더 이상 작성되지 않아야 한다."""
    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", _settings_with_kms())
    paths = [f["path"] for f in files]
    assert not any("/var/lib/rancher/k3s/agent/pod-manifests" in p for p in paths), (
        f"static pod manifest 가 여전히 작성됨: {paths}"
    )
    assert not any("barbican-kms.yaml" in p and "pod-manifests" in p for p in paths)


def test_extra_write_files_includes_systemd_unit():
    """barbican-kms.service systemd unit 파일이 작성되어야 한다."""
    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", _settings_with_kms())
    unit_files = [f for f in files if f["path"] == "/etc/systemd/system/barbican-kms.service"]
    assert len(unit_files) == 1
    content = unit_files[0]["content"]
    assert "[Unit]" in content
    assert "Before=k3s.service" in content, "k3s.service 보다 먼저 시작되어야 함 (데드락 방지)"
    assert "ExecStart=/usr/local/bin/barbican-kms-plugin" in content
    assert "--socketpath=/var/lib/kms/kms.sock" in content
    assert "--cloud-config=/etc/kubernetes/barbican-cloud.conf" in content
    assert "--key-id=kek-uuid-test" in content


def test_extra_write_files_includes_install_script():
    """install_kms.sh 가 0750 권한으로 작성되어야 한다."""
    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", _settings_with_kms())
    install_files = [f for f in files if f["path"] == "/opt/k3s/install_kms.sh"]
    assert len(install_files) == 1
    assert install_files[0]["permissions"] == "0750"
    content = install_files[0]["content"]
    assert "k3s ctr image pull" in content, "k3s ctr 로 image pull 해야 함"
    assert "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1" in content
    assert "/usr/local/bin/barbican-kms-plugin" in content


def test_extra_write_files_includes_encryption_config():
    """encryption-config.yaml 이 0600 권한으로 작성되어야 한다 (apiserver 가 부팅 시 읽음)."""
    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", _settings_with_kms())
    enc_files = [f for f in files if f["path"] == "/etc/kubernetes/encryption-config.yaml"]
    assert len(enc_files) == 1
    assert enc_files[0]["permissions"] == "0600"
    assert "kms" in enc_files[0]["content"].lower()
    assert "/var/lib/kms/kms.sock" in enc_files[0]["content"]


def test_extra_write_files_includes_cloud_conf():
    """barbican-cloud.conf 가 0600 권한으로 작성되어야 한다 (KMS plugin 이 인증에 사용)."""
    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", _settings_with_kms())
    cc_files = [f for f in files if f["path"] == "/etc/kubernetes/barbican-cloud.conf"]
    assert len(cc_files) == 1
    assert cc_files[0]["permissions"] == "0600"
    assert "[Global]" in cc_files[0]["content"]


def test_extra_write_files_returns_exactly_four_files():
    """PR3 후 정확히 4개 파일: systemd unit + install script + encryption-config + cloud.conf."""
    plugin = BarbicanKmsPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", _settings_with_kms())
    assert len(files) == 4


# ---------------------------------------------------------------------------
# server_install_args — pod-manifest-path 제거 + encryption-provider-config 유지
# ---------------------------------------------------------------------------


def test_server_install_args_drops_pod_manifest_path():
    """PR3 핵심: --kubelet-arg=pod-manifest-path 가 더 이상 필요 없어야 한다 (host static pod 폐기)."""
    plugin = BarbicanKmsPlugin()
    args = plugin.server_install_args(_settings_with_kms())
    assert not any("pod-manifest-path" in a for a in args), f"pod-manifest-path 인자가 여전히 존재: {args}"


def test_server_install_args_keeps_encryption_provider_config():
    """encryption-provider-config 인자는 여전히 필요 (apiserver 가 부팅 시 읽음)."""
    plugin = BarbicanKmsPlugin()
    args = plugin.server_install_args(_settings_with_kms())
    assert any("encryption-provider-config=/etc/kubernetes/encryption-config.yaml" in a for a in args)


# ---------------------------------------------------------------------------
# k3s_server.yaml.j2 cloud-init flow — barbican_kms_enabled 분기
# ---------------------------------------------------------------------------


def test_k3s_server_userdata_kms_enabled_uses_skip_start_and_waits_sock():
    """barbican_kms_enabled=True 시 cloud-init 가 INSTALL_K3S_SKIP_START + sock wait + manual k3s start 흐름이어야 한다."""
    import base64
    import gzip

    from app.services import k3s_cloudinit

    result = k3s_cloudinit.generate_server_userdata(
        cluster_name="test",
        k3s_version="v1.34.6+k3s1",
        callback_url="https://callback.example.com",
        callback_token="tok",
        cloud_conf="",
        plugin_manifests=[],
        extra_server_args=[],
        extra_write_files=[],
        extra_tls_sans=[],
        needs_external_cloud_provider=False,
        barbican_kms_enabled=True,
    )
    yaml_str = gzip.decompress(base64.b64decode(result.data)).decode()
    # KMS 활성화 시: SKIP_START 로 install 만 하고 KMS 준비 후 수동 start
    assert "INSTALL_K3S_SKIP_START=true" in yaml_str
    assert "/opt/k3s/install_kms.sh" in yaml_str
    assert "systemctl enable --now barbican-kms.service" in yaml_str
    assert "/var/lib/kms/kms.sock" in yaml_str
    assert "systemctl enable --now k3s.service" in yaml_str


def test_k3s_server_userdata_kms_disabled_uses_default_flow():
    """barbican_kms_enabled=False (기본) 시 기존 흐름 (k3s install 이 자동 start)."""
    import base64
    import gzip

    from app.services import k3s_cloudinit

    result = k3s_cloudinit.generate_server_userdata(
        cluster_name="test",
        k3s_version="v1.34.6+k3s1",
        callback_url="https://callback.example.com",
        callback_token="tok",
        cloud_conf="",
        plugin_manifests=[],
        extra_server_args=[],
        extra_write_files=[],
        extra_tls_sans=[],
        needs_external_cloud_provider=False,
        # barbican_kms_enabled=False (default)
    )
    yaml_str = gzip.decompress(base64.b64decode(result.data)).decode()
    assert "INSTALL_K3S_SKIP_START" not in yaml_str
    assert "install_kms.sh" not in yaml_str
    assert "barbican-kms.service" not in yaml_str
