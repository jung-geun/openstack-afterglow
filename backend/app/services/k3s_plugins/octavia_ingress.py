"""Octavia Ingress Controller Plugin — Ingress → Octavia LB 라우팅."""

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


class OctaviaIngressPlugin:
    name = "octavia_ingress"

    def should_deploy(self, settings: Settings) -> bool:
        if not settings.k3s_octavia_ingress_enabled:
            return False
        if not settings.os_auth_url or not settings.os_username or not settings.os_password:
            _logger.warning("OctaviaIngress 활성화됨이지만 OpenStack 인증 정보 미설정")
            return False
        if not settings.k3s_octavia_ingress_subnet_id:
            _logger.warning("OctaviaIngress 활성화됨이지만 octavia_ingress_subnet_id 미설정")
            return False
        return True

    def cloud_conf_sections(self, project_id: str, settings: Settings) -> str:
        return ""

    def generate_manifests(self, cluster_name: str, project_id: str, settings: Settings) -> str:
        return _jinja.get_template("k3s_plugins/octavia_ingress/manifests.yaml.j2").render(
            octavia_ingress_image=settings.k3s_octavia_ingress_image,
            cluster_name=cluster_name,
            os_auth_url=settings.os_auth_url,
            os_region=settings.os_region_name,
            os_username=settings.os_username,
            os_password=settings.os_password,
            os_domain=settings.os_user_domain_name,
            project_id=project_id,
            subnet_id=settings.k3s_octavia_ingress_subnet_id,
            floating_network_id=settings.k3s_octavia_ingress_floating_network_id,
        )

    def extra_write_files(self, project_id: str, cluster_name: str, settings: Settings) -> list[dict]:
        return []

    def server_install_args(self, settings: Settings) -> list[str]:
        return []

    def agent_install_args(self, settings: Settings) -> list[str]:
        return []

    def needs_external_cloud_provider(self, settings: Settings) -> bool:
        return False
