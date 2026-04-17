"""OCCM 하위호환 래퍼 — k3s_plugins.occm으로 위임.

신규 코드는 app.services.k3s_plugins 레지스트리를 직접 사용할 것.
"""

from app.config import Settings
from app.services.k3s_plugins.occm import OccmPlugin

_occm = OccmPlugin()


def should_deploy_occm(settings: Settings) -> bool:
    return _occm.should_deploy(settings)


def generate_cloud_conf(project_id: str, settings: Settings) -> str:
    return _occm.cloud_conf_sections(project_id, settings)


def generate_occm_manifests(cluster_name: str, settings: Settings) -> str:
    return _occm.generate_manifests(cluster_name, project_id="", settings=settings)
