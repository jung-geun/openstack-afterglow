"""k3s cloud-init 템플릿 렌더링."""

import base64
import gzip
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def generate_server_userdata(
    cluster_name: str,
    k3s_version: str,
    callback_url: str,
    callback_token: str,
    *,
    cloud_conf: str | None = None,
    plugin_manifests: list[dict] | None = None,  # [{"name": "occm", "content": "..."}]
    extra_server_args: list[str] | None = None,
    extra_write_files: list[dict] | None = None,
    needs_external_cloud_provider: bool = False,
    # 하위호환 파라미터 (deprecated — 레지스트리 우회 시에만 사용)
    occm_enabled: bool = False,
    occm_manifests: str | None = None,
) -> str:
    """k3s 서버 노드 cloud-init YAML을 렌더링하여 base64 인코딩 반환.

    신규 호출자는 plugin_manifests / extra_server_args / cloud_conf를 직접 전달할 것.
    occm_enabled + occm_manifests는 하위호환용으로만 유지.
    """
    # 하위호환: 구 occm_enabled 파라미터 지원
    if occm_enabled and occm_manifests and not plugin_manifests:
        plugin_manifests = [{"name": "occm", "content": occm_manifests}]
        needs_external_cloud_provider = True

    yaml_str = _jinja.get_template("k3s_server.yaml.j2").render(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        callback_url=callback_url,
        callback_token=callback_token,
        cloud_conf=cloud_conf or "",
        plugins=plugin_manifests or [],
        extra_server_args=extra_server_args or [],
        extra_write_files=extra_write_files or [],
        needs_external_cloud_provider=needs_external_cloud_provider,
    )
    # gzip 압축 후 base64 인코딩 — cloud-init이 gzip user_data를 자동 감지·처리.
    # 플러그인 매니페스트가 많을 때 Nova의 user_data 65535바이트 제한 초과를 방지한다.
    return base64.b64encode(gzip.compress(yaml_str.encode())).decode()


def generate_agent_userdata(
    cluster_name: str,
    k3s_version: str,
    server_ip: str,
    node_token: str,
    ssh_public_key: str | None = None,
    *,
    extra_agent_args: list[str] | None = None,
    # 하위호환 파라미터 (deprecated)
    occm_enabled: bool = False,
) -> str:
    """k3s 에이전트 노드 cloud-init YAML을 렌더링하여 base64 인코딩 반환."""
    if not node_token:
        raise ValueError("node_token이 비어있습니다. 서버 콜백에서 토큰이 전달되지 않았습니다.")

    # 하위호환: occm_enabled → cloud-provider=external
    agent_args = list(extra_agent_args or [])
    if occm_enabled and "--kubelet-arg=cloud-provider=external" not in agent_args:
        agent_args.append("--kubelet-arg=cloud-provider=external")

    yaml_str = _jinja.get_template("k3s_agent.yaml.j2").render(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        server_ip=server_ip,
        node_token=node_token,
        ssh_public_key=ssh_public_key or "",
        extra_agent_args=agent_args,
    )
    return base64.b64encode(gzip.compress(yaml_str.encode())).decode()
