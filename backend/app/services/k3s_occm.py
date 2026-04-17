"""OCCM (OpenStack Cloud Controller Manager) 설정 생성.

cloud.conf 및 OCCM 매니페스트를 Jinja2 템플릿으로 렌더링.
K3s 클러스터 생성 시 cloud-init에 포함되어 VM 내에서 자동 배포됨.
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.config import Settings

_logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def should_deploy_occm(settings: Settings) -> bool:
    """OCCM 배포 가능 여부 확인 (설정 완전성 검사)."""
    if not settings.k3s_occm_enabled:
        return False
    if not settings.os_auth_url:
        _logger.warning("OCCM 활성화됨이지만 os_auth_url 미설정")
        return False
    if not settings.os_username or not settings.os_password:
        _logger.warning("OCCM 활성화됨이지만 OpenStack 인증 정보 미설정")
        return False
    return True


def generate_cloud_conf(project_id: str, settings: Settings) -> str:
    """OCCM cloud.conf 렌더링."""
    tmpl = _jinja.get_template("occm/cloud_config.conf.j2")
    return tmpl.render(
        auth_url=settings.os_auth_url,
        region=settings.os_region_name,
        username=settings.os_username,
        password=settings.os_password,
        user_domain_name=settings.os_user_domain_name,
        project_id=project_id,
        ca_file="" if settings.os_insecure else (settings.os_cacert or ""),
        floating_network_id=settings.k3s_occm_floating_network_id,
        public_network_name=settings.k3s_occm_public_network_name,
    )


def generate_occm_manifests(cluster_name: str, settings: Settings) -> str:
    """OCCM RBAC + DaemonSet 매니페스트 렌더링."""
    tmpl = _jinja.get_template("occm/manifests.yaml.j2")
    return tmpl.render(
        occm_image=settings.k3s_occm_image,
        cluster_name=cluster_name,
    )
