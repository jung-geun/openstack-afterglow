"""K3s 플러그인 레지스트리.

활성 플러그인 집계 및 cloud-init 생성에 필요한 데이터를 제공한다.
"""

import logging

from app.config import Settings

from .barbican_kms import BarbicanKmsPlugin
from .cinder_csi import CinderCsiPlugin
from .keystone_auth import KeystoneAuthPlugin
from .manila_csi import ManilaCsiPlugin
from .occm import OccmPlugin
from .octavia_ingress import OctaviaIngressPlugin

_logger = logging.getLogger(__name__)

# 플러그인 등록 순서 = 배포 순서
ALL_PLUGINS = [
    OccmPlugin(),
    CinderCsiPlugin(),
    ManilaCsiPlugin(),
    OctaviaIngressPlugin(),
    KeystoneAuthPlugin(),
    BarbicanKmsPlugin(),
]


def get_active_plugins(settings: Settings) -> list:
    """설정에서 활성화된 플러그인 목록 반환."""
    return [p for p in ALL_PLUGINS if p.should_deploy(settings)]


def needs_external_cloud_provider(settings: Settings) -> bool:
    """하나 이상의 플러그인이 --disable-cloud-controller 필요 시 True."""
    return any(p.needs_external_cloud_provider(settings) for p in get_active_plugins(settings))


def aggregate_cloud_conf(project_id: str, settings: Settings) -> str | None:
    """활성 플러그인의 cloud.conf를 합산 반환.

    cloud.conf가 필요한 플러그인이 없으면 None 반환.
    [Global] 섹션은 OCCM 플러그인이 전체 내용으로 제공하며,
    다른 플러그인은 추가 섹션만 제공한다.
    """
    active = get_active_plugins(settings)
    sections: list[str] = []
    for plugin in active:
        section = plugin.cloud_conf_sections(project_id, settings)
        if section:
            sections.append(section.strip())

    if not sections:
        return None
    return "\n\n".join(sections) + "\n"


def aggregate_manifests(cluster_name: str, project_id: str, settings: Settings) -> list[dict[str, str]]:
    """활성 플러그인의 매니페스트 목록 반환.

    Returns:
        [{"name": "occm", "content": "..."}, ...]
    """
    result = []
    for plugin in get_active_plugins(settings):
        try:
            content = plugin.generate_manifests(cluster_name, project_id, settings)
            result.append({"name": plugin.name, "content": content})
        except Exception as e:
            _logger.warning("플러그인 %s 매니페스트 생성 실패 (스킵): %s", plugin.name, e)
    return result


def aggregate_extra_write_files(project_id: str, cluster_name: str, settings: Settings) -> list[dict]:
    """활성 플러그인의 추가 write_files 항목 합산."""
    result = []
    for plugin in get_active_plugins(settings):
        result.extend(plugin.extra_write_files(project_id, cluster_name, settings))
    return result


def aggregate_server_args(settings: Settings) -> list[str]:
    """활성 플러그인의 K3s 서버 인자 합산 (중복 제거, 순서 유지)."""
    seen = set()
    result = []
    for plugin in get_active_plugins(settings):
        for arg in plugin.server_install_args(settings):
            if arg not in seen:
                seen.add(arg)
                result.append(arg)
    return result


def aggregate_agent_args(settings: Settings) -> list[str]:
    """활성 플러그인의 K3s 에이전트 인자 합산 (중복 제거, 순서 유지)."""
    seen = set()
    result = []
    for plugin in get_active_plugins(settings):
        for arg in plugin.agent_install_args(settings):
            if arg not in seen:
                seen.add(arg)
                result.append(arg)
    return result


def get_active_plugin_names(settings: Settings) -> dict[str, bool]:
    """플러그인명 → True 매핑 반환 (DB 저장용)."""
    return {p.name: True for p in get_active_plugins(settings)}
