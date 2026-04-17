"""k3s_plugins 레지스트리 및 각 플러그인 단위 테스트."""

from unittest.mock import MagicMock

import yaml


def _base_settings(**kwargs) -> MagicMock:
    """테스트용 Settings MagicMock 생성."""
    defaults = {
        "os_auth_url": "https://keystone.example.com:5000/v3",
        "os_username": "admin",
        "os_password": "secret",
        "os_region_name": "RegionOne",
        "os_user_domain_name": "Default",
        "os_insecure": False,
        "os_cacert": "",
        # OCCM
        "k3s_occm_enabled": False,
        "k3s_occm_image": "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0",
        "k3s_occm_floating_network_id": "",
        "k3s_occm_public_network_name": "",
        # Cinder CSI
        "k3s_cinder_csi_enabled": False,
        "k3s_cinder_csi_image": "registry.k8s.io/provider-os/cinder-csi-plugin:v1.31.0",
        "k3s_cinder_csi_default_az": "nova",
        # Manila CSI
        "k3s_manila_csi_enabled": False,
        "k3s_manila_csi_image": "registry.k8s.io/provider-os/manila-csi-plugin:v1.31.0",
        "k3s_manila_csi_nfs_image": "registry.k8s.io/sig-storage/nfsplugin:v4.9.0",
        "k3s_manila_csi_share_protocol": "NFS",
        # Keystone Auth
        "k3s_keystone_auth_enabled": False,
        "k3s_keystone_auth_image": "registry.k8s.io/provider-os/k8s-keystone-auth:v1.31.0",
        "k3s_keystone_auth_policy": "",
        # Octavia Ingress
        "k3s_octavia_ingress_enabled": False,
        "k3s_octavia_ingress_image": "registry.k8s.io/provider-os/octavia-ingress-controller:v1.31.0",
        "k3s_octavia_ingress_subnet_id": "",
        "k3s_octavia_ingress_floating_network_id": "",
        # Barbican KMS
        "k3s_barbican_kms_enabled": False,
        "k3s_barbican_kms_image": "registry.k8s.io/provider-os/barbican-kms-plugin:v1.31.0",
        "k3s_barbican_kms_kek_id": "",
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# OCCM 플러그인
# ---------------------------------------------------------------------------


def test_occm_should_deploy_false_when_disabled():
    from app.services.k3s_plugins.occm import OccmPlugin

    s = _base_settings(k3s_occm_enabled=False)
    assert OccmPlugin().should_deploy(s) is False


def test_occm_should_deploy_false_when_no_auth_url():
    from app.services.k3s_plugins.occm import OccmPlugin

    s = _base_settings(k3s_occm_enabled=True, os_auth_url="")
    assert OccmPlugin().should_deploy(s) is False


def test_occm_should_deploy_true():
    from app.services.k3s_plugins.occm import OccmPlugin

    s = _base_settings(k3s_occm_enabled=True)
    assert OccmPlugin().should_deploy(s) is True


def test_occm_cloud_conf_sections_contains_global():
    from app.services.k3s_plugins.occm import OccmPlugin

    s = _base_settings(k3s_occm_enabled=True)
    result = OccmPlugin().cloud_conf_sections("proj-1", s)
    assert "[Global]" in result
    assert "auth-url=https://keystone.example.com:5000/v3" in result
    assert "tenant-id=proj-1" in result


def test_occm_manifests_valid_yaml():
    from app.services.k3s_plugins.occm import OccmPlugin

    s = _base_settings(k3s_occm_enabled=True)
    manifests = OccmPlugin().generate_manifests("test-cluster", "proj-1", s)
    docs = list(yaml.safe_load_all(manifests))
    assert len(docs) > 0
    kinds = {d["kind"] for d in docs if d}
    assert "DaemonSet" in kinds
    assert "ClusterRole" in kinds


def test_occm_needs_external_cloud_provider():
    from app.services.k3s_plugins.occm import OccmPlugin

    s = _base_settings(k3s_occm_enabled=True)
    assert OccmPlugin().needs_external_cloud_provider(s) is True


# ---------------------------------------------------------------------------
# Cinder CSI 플러그인
# ---------------------------------------------------------------------------


def test_cinder_csi_disabled_by_default():
    from app.services.k3s_plugins.cinder_csi import CinderCsiPlugin

    s = _base_settings()
    assert CinderCsiPlugin().should_deploy(s) is False


def test_cinder_csi_should_deploy_true():
    from app.services.k3s_plugins.cinder_csi import CinderCsiPlugin

    s = _base_settings(k3s_cinder_csi_enabled=True)
    assert CinderCsiPlugin().should_deploy(s) is True


def test_cinder_csi_manifests_valid_yaml():
    from app.services.k3s_plugins.cinder_csi import CinderCsiPlugin

    s = _base_settings(k3s_cinder_csi_enabled=True)
    manifests = CinderCsiPlugin().generate_manifests("test-cluster", "proj-1", s)
    docs = list(yaml.safe_load_all(manifests))
    kinds = {d["kind"] for d in docs if d}
    assert "CSIDriver" in kinds
    assert "StatefulSet" in kinds
    assert "DaemonSet" in kinds
    assert "StorageClass" in kinds


def test_cinder_csi_cloud_conf_section():
    from app.services.k3s_plugins.cinder_csi import CinderCsiPlugin

    s = _base_settings(k3s_cinder_csi_enabled=True)
    section = CinderCsiPlugin().cloud_conf_sections("proj-1", s)
    assert "[BlockStorage]" in section


def test_cinder_csi_no_external_cloud_provider():
    from app.services.k3s_plugins.cinder_csi import CinderCsiPlugin

    s = _base_settings(k3s_cinder_csi_enabled=True)
    assert CinderCsiPlugin().needs_external_cloud_provider(s) is False


# ---------------------------------------------------------------------------
# Manila CSI 플러그인
# ---------------------------------------------------------------------------


def test_manila_csi_disabled_by_default():
    from app.services.k3s_plugins.manila_csi import ManilaCsiPlugin

    s = _base_settings()
    assert ManilaCsiPlugin().should_deploy(s) is False


def test_manila_csi_should_deploy_true():
    from app.services.k3s_plugins.manila_csi import ManilaCsiPlugin

    s = _base_settings(k3s_manila_csi_enabled=True)
    assert ManilaCsiPlugin().should_deploy(s) is True


def test_manila_csi_manifests_valid_yaml():
    from app.services.k3s_plugins.manila_csi import ManilaCsiPlugin

    s = _base_settings(k3s_manila_csi_enabled=True)
    manifests = ManilaCsiPlugin().generate_manifests("test-cluster", "proj-1", s)
    docs = [d for d in yaml.safe_load_all(manifests) if d]
    kinds = {d["kind"] for d in docs}
    assert "CSIDriver" in kinds
    assert "StatefulSet" in kinds
    assert "StorageClass" in kinds
    # NFS CSI 드라이버도 포함되어야 함
    names = {d.get("metadata", {}).get("name") for d in docs}
    assert "nfs.csi.k8s.io" in names


def test_manila_csi_no_cloud_conf_sections():
    from app.services.k3s_plugins.manila_csi import ManilaCsiPlugin

    s = _base_settings(k3s_manila_csi_enabled=True)
    assert ManilaCsiPlugin().cloud_conf_sections("proj-1", s) == ""


# ---------------------------------------------------------------------------
# Octavia Ingress 플러그인
# ---------------------------------------------------------------------------


def test_octavia_ingress_disabled_by_default():
    from app.services.k3s_plugins.octavia_ingress import OctaviaIngressPlugin

    s = _base_settings()
    assert OctaviaIngressPlugin().should_deploy(s) is False


def test_octavia_ingress_requires_subnet_id():
    from app.services.k3s_plugins.octavia_ingress import OctaviaIngressPlugin

    s = _base_settings(
        k3s_octavia_ingress_enabled=True, k3s_octavia_ingress_subnet_id=""
    )
    assert OctaviaIngressPlugin().should_deploy(s) is False


def test_octavia_ingress_should_deploy_true():
    from app.services.k3s_plugins.octavia_ingress import OctaviaIngressPlugin

    s = _base_settings(
        k3s_octavia_ingress_enabled=True, k3s_octavia_ingress_subnet_id="subnet-123"
    )
    assert OctaviaIngressPlugin().should_deploy(s) is True


def test_octavia_ingress_manifests_valid_yaml():
    from app.services.k3s_plugins.octavia_ingress import OctaviaIngressPlugin

    s = _base_settings(
        k3s_octavia_ingress_enabled=True, k3s_octavia_ingress_subnet_id="subnet-123"
    )
    manifests = OctaviaIngressPlugin().generate_manifests("test-cluster", "proj-1", s)
    docs = [d for d in yaml.safe_load_all(manifests) if d]
    kinds = {d["kind"] for d in docs}
    assert "StatefulSet" in kinds
    assert "IngressClass" in kinds


# ---------------------------------------------------------------------------
# Keystone Auth 플러그인
# ---------------------------------------------------------------------------


def test_keystone_auth_disabled_by_default():
    from app.services.k3s_plugins.keystone_auth import KeystoneAuthPlugin

    s = _base_settings()
    assert KeystoneAuthPlugin().should_deploy(s) is False


def test_keystone_auth_should_deploy_true():
    from app.services.k3s_plugins.keystone_auth import KeystoneAuthPlugin

    s = _base_settings(k3s_keystone_auth_enabled=True)
    assert KeystoneAuthPlugin().should_deploy(s) is True


def test_keystone_auth_server_install_args():
    from app.services.k3s_plugins.keystone_auth import KeystoneAuthPlugin

    s = _base_settings(k3s_keystone_auth_enabled=True)
    args = KeystoneAuthPlugin().server_install_args(s)
    assert any("authentication-token-webhook-config-file" in a for a in args)


def test_keystone_auth_extra_write_files():
    from app.services.k3s_plugins.keystone_auth import KeystoneAuthPlugin

    s = _base_settings(k3s_keystone_auth_enabled=True)
    plugin = KeystoneAuthPlugin()
    files = plugin.extra_write_files("proj-1", "test-cluster", s)
    assert len(files) == 1
    assert files[0]["path"] == "/etc/kubernetes/keystone-webhook.yaml"
    assert "webhook" in files[0]["content"].lower()


def test_keystone_auth_manifests_valid_yaml():
    from app.services.k3s_plugins.keystone_auth import KeystoneAuthPlugin

    s = _base_settings(k3s_keystone_auth_enabled=True)
    plugin = KeystoneAuthPlugin()
    manifests = plugin.generate_manifests("test-cluster", "proj-1", s)
    docs = [d for d in yaml.safe_load_all(manifests) if d]
    kinds = {d["kind"] for d in docs}
    assert "Deployment" in kinds
    assert "Service" in kinds
    assert "Secret" in kinds


# ---------------------------------------------------------------------------
# Barbican KMS 플러그인
# ---------------------------------------------------------------------------


def test_barbican_kms_disabled_by_default():
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    s = _base_settings()
    assert BarbicanKmsPlugin().should_deploy(s) is False


def test_barbican_kms_requires_kek_id():
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    s = _base_settings(k3s_barbican_kms_enabled=True, k3s_barbican_kms_kek_id="")
    assert BarbicanKmsPlugin().should_deploy(s) is False


def test_barbican_kms_should_deploy_true():
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    s = _base_settings(
        k3s_barbican_kms_enabled=True, k3s_barbican_kms_kek_id="kek-uuid-123"
    )
    assert BarbicanKmsPlugin().should_deploy(s) is True


def test_barbican_kms_server_install_args():
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    s = _base_settings(
        k3s_barbican_kms_enabled=True, k3s_barbican_kms_kek_id="kek-uuid-123"
    )
    args = BarbicanKmsPlugin().server_install_args(s)
    assert any("encryption-provider-config" in a for a in args)


def test_barbican_kms_extra_write_files():
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    s = _base_settings(
        k3s_barbican_kms_enabled=True, k3s_barbican_kms_kek_id="kek-uuid-123"
    )
    files = BarbicanKmsPlugin().extra_write_files("proj-1", "test-cluster", s)
    assert len(files) == 1
    assert files[0]["path"] == "/etc/kubernetes/encryption-config.yaml"


def test_barbican_kms_manifests_valid_yaml():
    from app.services.k3s_plugins.barbican_kms import BarbicanKmsPlugin

    s = _base_settings(
        k3s_barbican_kms_enabled=True, k3s_barbican_kms_kek_id="kek-uuid-123"
    )
    manifests = BarbicanKmsPlugin().generate_manifests("test-cluster", "proj-1", s)
    docs = [d for d in yaml.safe_load_all(manifests) if d]
    kinds = {d["kind"] for d in docs}
    assert "DaemonSet" in kinds


# ---------------------------------------------------------------------------
# 레지스트리 집계 함수
# ---------------------------------------------------------------------------


def test_registry_no_plugins_active():
    from app.services import k3s_plugins

    s = _base_settings()
    assert k3s_plugins.get_active_plugins(s) == []
    assert k3s_plugins.needs_external_cloud_provider(s) is False
    assert k3s_plugins.aggregate_cloud_conf("proj-1", s) is None
    assert k3s_plugins.aggregate_manifests("test-cluster", "proj-1", s) == []


def test_registry_occm_only():
    from app.services import k3s_plugins

    s = _base_settings(k3s_occm_enabled=True)
    active = k3s_plugins.get_active_plugins(s)
    assert len(active) == 1
    assert active[0].name == "occm"
    assert k3s_plugins.needs_external_cloud_provider(s) is True
    cloud_conf = k3s_plugins.aggregate_cloud_conf("proj-1", s)
    assert cloud_conf is not None
    assert "[Global]" in cloud_conf


def test_registry_occm_plus_cinder():
    from app.services import k3s_plugins

    s = _base_settings(k3s_occm_enabled=True, k3s_cinder_csi_enabled=True)
    active = k3s_plugins.get_active_plugins(s)
    assert len(active) == 2
    cloud_conf = k3s_plugins.aggregate_cloud_conf("proj-1", s)
    assert "[Global]" in cloud_conf
    assert "[BlockStorage]" in cloud_conf
    manifests = k3s_plugins.aggregate_manifests("test-cluster", "proj-1", s)
    assert len(manifests) == 2
    names = [m["name"] for m in manifests]
    assert "occm" in names
    assert "cinder_csi" in names


def test_registry_server_args_dedup():
    """동일 인자가 여러 플러그인에서 반환되어도 중복 없어야 함."""
    from app.services import k3s_plugins

    class FakePluginA:
        name = "fake_a"

        def should_deploy(self, s):
            return True

        def cloud_conf_sections(self, pid, s):
            return ""

        def generate_manifests(self, cn, pid, s):
            return ""

        def extra_write_files(self, pid, cn, s):
            return []

        def server_install_args(self, s):
            return ["--foo=bar", "--baz=1"]

        def agent_install_args(self, s):
            return []

        def needs_external_cloud_provider(self, s):
            return False

    class FakePluginB:
        name = "fake_b"

        def should_deploy(self, s):
            return True

        def cloud_conf_sections(self, pid, s):
            return ""

        def generate_manifests(self, cn, pid, s):
            return ""

        def extra_write_files(self, pid, cn, s):
            return []

        def server_install_args(self, s):
            return ["--foo=bar", "--other=x"]  # --foo=bar 중복

        def agent_install_args(self, s):
            return []

        def needs_external_cloud_provider(self, s):
            return False

    original = k3s_plugins.ALL_PLUGINS
    k3s_plugins.ALL_PLUGINS = [FakePluginA(), FakePluginB()]
    try:
        s = _base_settings()
        args = k3s_plugins.aggregate_server_args(s)
        assert args.count("--foo=bar") == 1
        assert "--baz=1" in args
        assert "--other=x" in args
    finally:
        k3s_plugins.ALL_PLUGINS = original


def test_registry_get_active_plugin_names():
    from app.services import k3s_plugins

    s = _base_settings(k3s_occm_enabled=True, k3s_cinder_csi_enabled=True)
    names = k3s_plugins.get_active_plugin_names(s)
    assert names == {"occm": True, "cinder_csi": True}


# ---------------------------------------------------------------------------
# cloud-init 통합 렌더링 테스트
# ---------------------------------------------------------------------------


def test_cloudinit_server_no_plugins():
    """플러그인 없을 때 cloud-init 렌더링이 정상 동작해야 한다."""
    import base64

    from app.services.k3s_cloudinit import generate_server_userdata

    result = generate_server_userdata(
        cluster_name="test",
        k3s_version="v1.31.4+k3s1",
        callback_url="http://callback.example.com",
        callback_token="token123",
    )
    decoded = base64.b64decode(result).decode()
    assert "#cloud-config" in decoded
    assert "k3s_version" not in decoded  # Jinja 변수 미치환 없어야 함
    assert "--disable-cloud-controller" not in decoded


def test_cloudinit_server_with_occm_plugin():
    """OCCM 플러그인 활성 시 cloud-init에 external cloud provider 인자가 포함되어야 한다."""
    import base64

    from app.services.k3s_cloudinit import generate_server_userdata

    result = generate_server_userdata(
        cluster_name="test",
        k3s_version="v1.31.4+k3s1",
        callback_url="http://callback.example.com",
        callback_token="token123",
        cloud_conf="[Global]\nauth-url=https://example.com\n",
        plugin_manifests=[
            {"name": "occm", "content": "apiVersion: v1\nkind: List\nitems: []\n"}
        ],
        needs_external_cloud_provider=True,
    )
    decoded = base64.b64decode(result).decode()
    assert "--disable-cloud-controller" in decoded
    assert "cloud-provider=external" in decoded
    assert "occm-manifests.yaml" in decoded
    assert "cloud.conf" in decoded


def test_cloudinit_server_multi_plugins():
    """복수 플러그인 시 각 매니페스트 파일이 write_files에 포함되어야 한다."""
    import base64

    from app.services.k3s_cloudinit import generate_server_userdata

    result = generate_server_userdata(
        cluster_name="test",
        k3s_version="v1.31.4+k3s1",
        callback_url="http://callback.example.com",
        callback_token="token123",
        plugin_manifests=[
            {"name": "occm", "content": "---\n# occm manifest\n"},
            {"name": "cinder_csi", "content": "---\n# cinder manifest\n"},
        ],
        needs_external_cloud_provider=True,
    )
    decoded = base64.b64decode(result).decode()
    assert "occm-manifests.yaml" in decoded
    assert "cinder_csi-manifests.yaml" in decoded


def test_cloudinit_agent_no_extra_args():
    """에이전트: extra_agent_args 없을 때 INSTALL_K3S_EXEC 없어야 한다."""
    import base64

    from app.services.k3s_cloudinit import generate_agent_userdata

    result = generate_agent_userdata(
        cluster_name="test",
        k3s_version="v1.31.4+k3s1",
        server_ip="10.0.0.1",
        node_token="tok",
    )
    decoded = base64.b64decode(result).decode()
    assert "#cloud-config" in decoded
    assert "INSTALL_K3S_EXEC" not in decoded


def test_cloudinit_agent_with_cloud_provider():
    """에이전트: extra_agent_args에 cloud-provider=external이 포함되어야 한다."""
    import base64

    from app.services.k3s_cloudinit import generate_agent_userdata

    result = generate_agent_userdata(
        cluster_name="test",
        k3s_version="v1.31.4+k3s1",
        server_ip="10.0.0.1",
        node_token="tok",
        extra_agent_args=["--kubelet-arg=cloud-provider=external"],
    )
    decoded = base64.b64decode(result).decode()
    assert "cloud-provider=external" in decoded
    assert "INSTALL_K3S_EXEC" in decoded


def test_cloudinit_agent_backward_compat_occm_enabled():
    """하위호환: occm_enabled=True 시 cloud-provider=external이 포함되어야 한다."""
    import base64

    from app.services.k3s_cloudinit import generate_agent_userdata

    result = generate_agent_userdata(
        cluster_name="test",
        k3s_version="v1.31.4+k3s1",
        server_ip="10.0.0.1",
        node_token="tok",
        occm_enabled=True,
    )
    decoded = base64.b64decode(result).decode()
    assert "cloud-provider=external" in decoded
