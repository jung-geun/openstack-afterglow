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
        # KMS 데몬 소켓(unix:///var/lib/kms/kms.sock)이 부팅 시점엔 존재하지 않아
        # kube-apiserver가 encryption-provider-config 초기화에서 데드락에 빠짐.
        # host static pod 방식으로 재설계할 때까지 강제 비활성화.
        if settings.k3s_barbican_kms_enabled:
            _logger.warning(
                "Barbican KMS는 현재 부팅 데드락으로 인해 비활성화되어 있습니다. "
                "host static pod 재설계 후 재활성화 예정."
            )
        return False

    def cloud_conf_sections(self, project_id: str, settings: Settings) -> str:
        """[KeyManager] 섹션 추가."""
        return "[KeyManager]\nuse-barbican=true\n"

    def generate_manifests(self, cluster_name: str, project_id: str, settings: Settings, **kwargs) -> str:
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
