"""OCCM 설정 생성 및 cloud-init 통합 단위 테스트."""

from unittest.mock import MagicMock

import pytest


def _make_settings(**overrides):
    """테스트용 Settings mock 생성."""
    defaults = {
        "k3s_occm_enabled": True,
        "k3s_occm_image": "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0",
        "k3s_occm_floating_network_id": "ext-net-id",
        "k3s_occm_public_network_name": "external",
        "os_auth_url": "https://keystone.example.com:5000/v3",
        "os_region_name": "RegionOne",
        "os_username": "admin",
        "os_password": "secret",
        "os_user_domain_name": "Default",
        "os_insecure": False,
        "os_cacert": "",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


class TestShouldDeployOccm:
    def test_enabled_with_all_fields(self):
        from app.services.k3s_occm import should_deploy_occm

        assert should_deploy_occm(_make_settings()) is True

    def test_disabled(self):
        from app.services.k3s_occm import should_deploy_occm

        assert should_deploy_occm(_make_settings(k3s_occm_enabled=False)) is False

    def test_missing_auth_url(self):
        from app.services.k3s_occm import should_deploy_occm

        assert should_deploy_occm(_make_settings(os_auth_url="")) is False

    def test_missing_credentials(self):
        from app.services.k3s_occm import should_deploy_occm

        assert should_deploy_occm(_make_settings(os_username="")) is False
        assert should_deploy_occm(_make_settings(os_password="")) is False


class TestGenerateCloudConf:
    def test_basic_render(self):
        from app.services.k3s_occm import generate_cloud_conf

        result = generate_cloud_conf("proj-123", _make_settings())
        assert "[Global]" in result
        assert "auth-url=https://keystone.example.com:5000/v3" in result
        assert "region=RegionOne" in result
        assert "username=admin" in result
        assert "tenant-id=proj-123" in result
        assert "[LoadBalancer]" in result
        assert "floating-network-id=ext-net-id" in result
        assert "[Networking]" in result
        assert "public-network-name=external" in result

    def test_no_floating_network(self):
        from app.services.k3s_occm import generate_cloud_conf

        result = generate_cloud_conf("proj-123", _make_settings(k3s_occm_floating_network_id=""))
        assert "floating-network-id" not in result

    def test_no_public_network_name(self):
        from app.services.k3s_occm import generate_cloud_conf

        result = generate_cloud_conf("proj-123", _make_settings(k3s_occm_public_network_name=""))
        assert "public-network-name" not in result

    def test_ca_file_included_when_not_insecure(self):
        from app.services.k3s_occm import generate_cloud_conf

        result = generate_cloud_conf("proj-123", _make_settings(os_cacert="/etc/ssl/ca.pem"))
        assert "ca-file=/etc/ssl/ca.pem" in result

    def test_no_ca_file_when_insecure(self):
        from app.services.k3s_occm import generate_cloud_conf

        result = generate_cloud_conf("proj-123", _make_settings(os_insecure=True))
        assert "ca-file" not in result


class TestGenerateOccmManifests:
    def test_basic_render(self):
        from app.services.k3s_occm import generate_occm_manifests

        result = generate_occm_manifests("my-cluster", _make_settings())
        assert "openstack-cloud-controller-manager" in result
        assert "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0" in result
        assert "my-cluster" in result
        assert "ServiceAccount" in result
        assert "ClusterRole" in result
        assert "DaemonSet" in result

    def test_custom_image(self):
        from app.services.k3s_occm import generate_occm_manifests

        result = generate_occm_manifests("test", _make_settings(k3s_occm_image="custom-reg/occm:v1.30.0"))
        assert "custom-reg/occm:v1.30.0" in result


class TestCloudInitIntegration:
    def test_server_userdata_without_occm(self):
        """OCCM 비활성 시 기존 템플릿 사용 확인."""
        import base64

        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok-123",
        )
        decoded = base64.b64decode(result).decode()
        assert "--disable-cloud-controller" not in decoded
        assert "cloud.conf" not in decoded

    def test_server_userdata_with_occm(self):
        """OCCM 활성 시 OCCM 템플릿 사용 + 필수 내용 포함 확인."""
        import base64

        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok-123",
            occm_enabled=True,
            cloud_conf="[Global]\nauth-url=http://keystone:5000/v3",
            occm_manifests="apiVersion: v1\nkind: ServiceAccount",
        )
        decoded = base64.b64decode(result).decode()
        assert "--disable-cloud-controller" in decoded
        assert '--kubelet-arg="cloud-provider=external"' in decoded
        assert "/etc/kubernetes/cloud.conf" in decoded
        assert "occm-manifests.yaml" in decoded
        assert "OCCM_STATUS" in decoded

    def test_agent_userdata_without_occm(self):
        """OCCM 비활성 시 기존 에이전트 템플릿."""
        import base64

        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="token-abc",
        )
        decoded = base64.b64decode(result).decode()
        assert "cloud-provider=external" not in decoded

    def test_agent_userdata_with_occm(self):
        """OCCM 활성 시 에이전트에 cloud-provider=external 포함."""
        import base64

        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="token-abc",
            occm_enabled=True,
        )
        decoded = base64.b64decode(result).decode()
        assert "cloud-provider=external" in decoded


class TestCallbackOccmStatus:
    def test_callback_request_has_occm_status(self):
        """K3sCallbackRequest에 occm_status 필드 존재 확인."""
        from app.models.k3s import K3sCallbackRequest

        req = K3sCallbackRequest(
            token="tok-1",
            success=True,
            kubeconfig="kc",
            node_token="nt",
            server_ip="10.0.0.1",
            occm_status="deployed",
        )
        assert req.occm_status == "deployed"

    def test_callback_request_occm_status_optional(self):
        """occm_status가 None이어도 유효한 요청."""
        from app.models.k3s import K3sCallbackRequest

        req = K3sCallbackRequest(token="tok-1", success=True)
        assert req.occm_status is None
