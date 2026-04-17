"""Barbican KMS Plugin — K8s Secret를 Barbican으로 암호화."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.config import Settings

_logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


class BarbicanKmsPlugin:
    name = "barbican_kms"

    def should_deploy(self, settings: Settings) -> bool:
        if not settings.k3s_barbican_kms_enabled:
            return False
        if not settings.os_auth_url or not settings.os_username or not settings.os_password:
            _logger.warning("BarbicanKMS 활성화됨이지만 OpenStack 인증 정보 미설정")
            return False
        if not settings.k3s_barbican_kms_kek_id:
            _logger.warning("BarbicanKMS 활성화됨이지만 barbican_kms_kek_id 미설정")
            return False
        return True

    def cloud_conf_sections(self, project_id: str, settings: Settings) -> str:
        """[KeyManager] 섹션 추가."""
        return "[KeyManager]\nuse-barbican=true\n"

    def generate_manifests(self, cluster_name: str, project_id: str, settings: Settings) -> str:
        return _jinja.get_template("k3s_plugins/barbican_kms/manifests.yaml.j2").render(
            barbican_kms_image=settings.k3s_barbican_kms_image,
            kek_id=settings.k3s_barbican_kms_kek_id,
        )

    def extra_write_files(self, project_id: str, cluster_name: str, settings: Settings) -> list[dict]:
        """encryption-config.yaml을 /etc/kubernetes/에 작성."""
        encryption_config = _jinja.get_template("k3s_plugins/barbican_kms/encryption_config.yaml.j2").render()
        return [
            {
                "path": "/etc/kubernetes/encryption-config.yaml",
                "permissions": "0600",
                "content": encryption_config,
            }
        ]

    def server_install_args(self, settings: Settings) -> list[str]:
        return [
            "--kube-apiserver-arg=encryption-provider-config=/etc/kubernetes/encryption-config.yaml",
        ]

    def agent_install_args(self, settings: Settings) -> list[str]:
        return []

    def needs_external_cloud_provider(self, settings: Settings) -> bool:
        return False
