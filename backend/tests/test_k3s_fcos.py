"""FCOS (Fedora CoreOS) k3s 노드 지원 테스트."""

import base64
import json

import pytest


class TestFCOSServerUserdata:
    def test_fcos_server_returns_ignition_json(self):
        """FCOS 서버 userdata가 유효한 Ignition JSON을 반환해야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test-cluster",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok-fcos",
            os_type="fcos",
        )
        assert result.config_drive is True
        ign = json.loads(result.data)
        assert ign["ignition"]["version"] == "3.4.0"

    def test_fcos_server_ignition_has_required_files(self):
        """FCOS Ignition에 callback.sh와 install.sh가 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="my-cluster",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok-fcos",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        paths = {f["path"] for f in ign["storage"]["files"]}
        assert "/opt/k3s/callback.sh" in paths
        assert "/opt/k3s/install.sh" in paths
        assert "/etc/systemd/system/k3s-install.service" in paths

    def test_fcos_server_ignition_k3s_install_enabled(self):
        """FCOS Ignition에서 k3s-install.service가 enabled여야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="my-cluster",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok-fcos",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        units = {u["name"]: u for u in ign["systemd"]["units"]}
        assert "k3s-install.service" in units
        assert units["k3s-install.service"]["enabled"] is True

    def test_fcos_server_ignition_with_cloud_conf(self):
        """FCOS Ignition에 cloud.conf 파일이 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok",
            cloud_conf="[Global]\nauth-url=https://keystone:5000/v3\n",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        files = {f["path"]: f for f in ign["storage"]["files"]}
        assert "/etc/kubernetes/cloud.conf" in files
        # 권한 0600 = 384
        assert files["/etc/kubernetes/cloud.conf"]["mode"] == 0o600

    def test_fcos_server_ignition_with_plugins(self):
        """FCOS Ignition에 플러그인 매니페스트 파일이 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok",
            plugin_manifests=[
                {"name": "occm", "content": "apiVersion: v1\nkind: List\n"},
                {"name": "cinder_csi", "content": "apiVersion: v1\nkind: List\n"},
            ],
            needs_external_cloud_provider=True,
            os_type="fcos",
        )
        ign = json.loads(result.data)
        paths = {f["path"] for f in ign["storage"]["files"]}
        assert "/opt/k3s/occm-manifests.yaml" in paths
        assert "/opt/k3s/cinder_csi-manifests.yaml" in paths

        # install.sh에 --disable-cloud-controller가 포함되어야 함
        files = {f["path"]: f for f in ign["storage"]["files"]}
        install_b64 = files["/opt/k3s/install.sh"]["contents"]["source"].split(",", 1)[1]
        install_content = base64.b64decode(install_b64).decode()
        assert "--disable-cloud-controller" in install_content

    def test_fcos_server_ignition_tls_san(self):
        """FCOS Ignition install.sh에 extra_tls_sans가 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="tok",
            extra_tls_sans=["203.0.113.10"],
            os_type="fcos",
        )
        ign = json.loads(result.data)
        files = {f["path"]: f for f in ign["storage"]["files"]}
        install_b64 = files["/opt/k3s/install.sh"]["contents"]["source"].split(",", 1)[1]
        install_content = base64.b64decode(install_b64).decode()
        assert "203.0.113.10" in install_content

    def test_fcos_server_callback_contains_token(self):
        """FCOS callback.sh에 올바른 토큰이 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_server_userdata

        result = generate_server_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            callback_url="http://api.example.com",
            callback_token="supersecrettoken",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        files = {f["path"]: f for f in ign["storage"]["files"]}
        cb_b64 = files["/opt/k3s/callback.sh"]["contents"]["source"].split(",", 1)[1]
        cb_content = base64.b64decode(cb_b64).decode()
        assert "supersecrettoken" in cb_content
        assert "http://api.example.com" in cb_content


class TestFCOSAgentUserdata:
    def test_fcos_agent_returns_ignition_json(self):
        """FCOS 에이전트 userdata가 유효한 Ignition JSON을 반환해야 한다."""
        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="node-token-abc",
            os_type="fcos",
        )
        assert result.config_drive is True
        ign = json.loads(result.data)
        assert ign["ignition"]["version"] == "3.4.0"

    def test_fcos_agent_ignition_has_required_files(self):
        """FCOS 에이전트 Ignition에 agent-join.sh가 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="node-token-abc",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        paths = {f["path"] for f in ign["storage"]["files"]}
        assert "/opt/k3s/agent-join.sh" in paths
        assert "/etc/systemd/system/k3s-agent-join.service" in paths

    def test_fcos_agent_ignition_agent_join_enabled(self):
        """FCOS 에이전트 Ignition에서 k3s-agent-join.service가 enabled여야 한다."""
        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="node-token-abc",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        units = {u["name"]: u for u in ign["systemd"]["units"]}
        assert "k3s-agent-join.service" in units
        assert units["k3s-agent-join.service"]["enabled"] is True

    def test_fcos_agent_ignition_with_ssh_key(self):
        """FCOS 에이전트 Ignition에 SSH 공개키가 passwd.users에 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="tok",
            ssh_public_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5 test@host",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        assert "passwd" in ign
        users = {u["name"]: u for u in ign["passwd"]["users"]}
        assert "core" in users
        assert "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5 test@host" in users["core"]["sshAuthorizedKeys"]

    def test_fcos_agent_ignition_without_ssh_key(self):
        """SSH 키 없을 때 FCOS 에이전트 Ignition에 passwd 섹션이 없어야 한다."""
        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="10.0.0.1",
            node_token="tok",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        assert "passwd" not in ign

    def test_fcos_agent_join_script_contains_server_ip(self):
        """FCOS 에이전트 join 스크립트에 서버 IP가 포함되어야 한다."""
        from app.services.k3s_cloudinit import generate_agent_userdata

        result = generate_agent_userdata(
            cluster_name="test",
            k3s_version="v1.31.4+k3s1",
            server_ip="192.168.1.100",
            node_token="tok",
            os_type="fcos",
        )
        ign = json.loads(result.data)
        files = {f["path"]: f for f in ign["storage"]["files"]}
        join_b64 = files["/opt/k3s/agent-join.sh"]["contents"]["source"].split(",", 1)[1]
        join_content = base64.b64decode(join_b64).decode()
        assert "192.168.1.100" in join_content
        assert "INSTALL_K3S_SKIP_SELINUX_RPM=true" in join_content


class TestFCOSOsTypeValidation:
    def test_invalid_os_type_raises_error(self):
        """잘못된 os_type은 ValidationError를 발생시켜야 한다."""
        from pydantic import ValidationError

        from app.models.k3s import CreateK3sClusterRequest

        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", os_type="windows")

    def test_valid_ubuntu_os_type(self):
        """ubuntu os_type은 유효해야 한다."""
        from app.models.k3s import CreateK3sClusterRequest

        req = CreateK3sClusterRequest(name="test", os_type="ubuntu")
        assert req.os_type == "ubuntu"

    def test_valid_fcos_os_type(self):
        """fcos os_type은 유효해야 한다."""
        from app.models.k3s import CreateK3sClusterRequest

        req = CreateK3sClusterRequest(name="test", os_type="fcos")
        assert req.os_type == "fcos"

    def test_default_os_type_is_ubuntu(self):
        """os_type 미지정 시 기본값이 ubuntu여야 한다."""
        from app.models.k3s import CreateK3sClusterRequest

        req = CreateK3sClusterRequest(name="test")
        assert req.os_type == "ubuntu"
