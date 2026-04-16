"""k3s cloud-init 템플릿 렌더링."""

import base64
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
) -> str:
    """k3s 서버 노드 cloud-init YAML을 렌더링하여 base64 인코딩 반환."""
    yaml_str = _jinja.get_template("k3s_server.yaml.j2").render(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        callback_url=callback_url,
        callback_token=callback_token,
    )
    return base64.b64encode(yaml_str.encode()).decode()


def generate_agent_userdata(
    cluster_name: str,
    k3s_version: str,
    server_ip: str,
    node_token: str,
    ssh_public_key: str | None = None,
) -> str:
    """k3s 에이전트 노드 cloud-init YAML을 렌더링하여 base64 인코딩 반환."""
    if not node_token:
        raise ValueError("node_token이 비어있습니다. 서버 콜백에서 토큰이 전달되지 않았습니다.")
    yaml_str = _jinja.get_template("k3s_agent.yaml.j2").render(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        server_ip=server_ip,
        node_token=node_token,
        ssh_public_key=ssh_public_key or "",
    )
    return base64.b64encode(yaml_str.encode()).decode()
