"""k3s cloud-init / Ignition 템플릿 렌더링."""

import base64
import gzip
import json
import re
from pathlib import Path
from typing import NamedTuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

OS_TYPE_UBUNTU = "ubuntu"
OS_TYPE_FCOS = "fcos"
VALID_OS_TYPES = {OS_TYPE_UBUNTU, OS_TYPE_FCOS}

# SSH 공개키 형식 검증 패턴 (개행 및 YAML injection 방지)
_SSH_KEY_RE = re.compile(
    r"^(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256|ecdsa-sha2-nistp384|ecdsa-sha2-nistp521|sk-ssh-ed25519@openssh\.com|sk-ecdsa-sha2-nistp256@openssh\.com)"
    r"\s+[A-Za-z0-9+/=]+"
    r"(\s+\S+)?$"
)


def _validate_ssh_public_key(key: str) -> None:
    """SSH 공개키 형식 검증. 유효하지 않으면 ValueError 발생."""
    if "\n" in key or "\r" in key:
        raise ValueError("SSH 공개키에 개행 문자가 포함될 수 없습니다")
    if not _SSH_KEY_RE.match(key.strip()):
        raise ValueError(f"유효하지 않은 SSH 공개키 형식입니다: {key[:40]!r}...")


class UserdataResult(NamedTuple):
    """cloud-init 또는 Ignition userdata 렌더링 결과."""

    data: str  # Nova user_data로 전달할 값
    config_drive: bool  # FCOS는 config_drive=True 필요


def _b64(text: str) -> str:
    """문자열을 base64로 인코딩하여 반환."""
    return base64.b64encode(text.encode()).decode()


def _ignition_file(path: str, content: str, mode: int = 0o644) -> dict:
    """Ignition storage.files 항목 생성 (gzip 압축으로 user_data 크기 절감)."""
    compressed = gzip.compress(content.encode())
    b64 = base64.b64encode(compressed).decode()
    return {
        "path": path,
        "mode": mode,
        "contents": {
            "compression": "gzip",
            "source": f"data:;base64,{b64}",
        },
    }


def _build_server_ignition(
    cluster_name: str,
    k3s_version: str,
    callback_url: str,
    callback_token: str,
    cloud_conf: str,
    plugins: list[dict],
    extra_server_args: list[str],
    extra_write_files: list[dict],
    extra_tls_sans: list[str],
    needs_external_cloud_provider: bool,
    server_node_name: str = "",
) -> str:
    """FCOS k3s 서버 노드 Ignition JSON 생성."""
    template_vars = dict(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        callback_url=callback_url,
        callback_token=callback_token,
        cloud_conf=cloud_conf,
        plugins=plugins,
        extra_server_args=extra_server_args,
        extra_tls_sans=extra_tls_sans,
        needs_external_cloud_provider=needs_external_cloud_provider,
    )

    callback_sh = _jinja.get_template("k3s_server_fcos_callback.sh.j2").render(**template_vars)

    # k3s 설치 스크립트 (systemd ExecStart용)
    tls_sans_args = " ".join(f'--tls-san "{san}"' for san in extra_tls_sans)
    cloud_controller_args = ""
    if needs_external_cloud_provider:
        cloud_controller_args = '--disable-cloud-controller --kubelet-arg="cloud-provider=external"'
    extra_args_str = " ".join(extra_server_args) if extra_server_args else ""

    node_name = server_node_name or f"{cluster_name}-server"
    install_script = f"""#!/bin/bash
set -e
SERVER_IP=$(hostname -I | awk '{{print $1}}')
curl -sfL https://get.k3s.io | \\
  INSTALL_K3S_VERSION="{k3s_version}" \\
  INSTALL_K3S_SKIP_SELINUX_RPM=true \\
  sh -s - server \\
    --tls-san "${{SERVER_IP}}" \\
    {tls_sans_args} \\
    --write-kubeconfig-mode 644 \\
    {cloud_controller_args} \\
    {extra_args_str} \\
    --node-name="{node_name}"
nohup /bin/bash /opt/k3s/callback.sh > /var/log/k3s-callback.log 2>&1 &
"""

    install_unit = f"""[Unit]
Description=K3s Server Install - {cluster_name}
After=network-online.target
Wants=network-online.target
ConditionPathExists=!/etc/rancher/k3s/k3s.yaml

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash /opt/k3s/install.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    files: list[dict] = []

    if cloud_conf:
        files.append(_ignition_file("/etc/kubernetes/cloud.conf", cloud_conf, mode=0o600))

    for plugin in plugins:
        files.append(_ignition_file(f"/opt/k3s/{plugin['name']}-manifests.yaml", plugin["content"], mode=0o644))

    for wf in extra_write_files:
        mode = int(wf.get("permissions", "0644"), 8)
        files.append(_ignition_file(wf["path"], wf["content"], mode=mode))

    files.append(_ignition_file("/opt/k3s/callback.sh", callback_sh, mode=0o750))
    files.append(_ignition_file("/opt/k3s/install.sh", install_script, mode=0o750))
    files.append(_ignition_file("/etc/systemd/system/k3s-install.service", install_unit, mode=0o644))

    ignition = {
        "ignition": {"version": "3.4.0"},
        "storage": {"files": files},
        "systemd": {
            "units": [
                {"name": "k3s-install.service", "enabled": True},
            ]
        },
    }

    return json.dumps(ignition)


def _build_agent_ignition(
    cluster_name: str,
    k3s_version: str,
    server_ip: str,
    node_token: str,
    ssh_public_key: str,
    extra_agent_args: list[str],
) -> str:
    """FCOS k3s 에이전트 노드 Ignition JSON 생성."""
    template_vars = dict(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        server_ip=server_ip,
        node_token=node_token,
        extra_agent_args=extra_agent_args,
    )
    join_sh = _jinja.get_template("k3s_agent_fcos_join.sh.j2").render(**template_vars)

    join_unit = f"""[Unit]
Description=K3s Agent Join - {cluster_name}
After=network-online.target
Wants=network-online.target
ConditionPathExists=!/etc/systemd/system/k3s-agent.service

[Service]
Type=oneshot
ExecStart=/bin/bash /opt/k3s/agent-join.sh
Restart=on-failure
RestartSec=120
StartLimitIntervalSec=14400
StartLimitBurst=20
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    files: list[dict] = [
        _ignition_file("/opt/k3s/agent-join.sh", join_sh, mode=0o750),
        _ignition_file("/etc/systemd/system/k3s-agent-join.service", join_unit, mode=0o644),
    ]

    passwd: dict = {}
    if ssh_public_key:
        passwd = {"users": [{"name": "core", "sshAuthorizedKeys": [ssh_public_key]}]}

    ignition: dict = {
        "ignition": {"version": "3.4.0"},
        "storage": {"files": files},
        "systemd": {
            "units": [
                {"name": "k3s-agent-join.service", "enabled": True},
            ]
        },
    }
    if passwd:
        ignition["passwd"] = passwd

    return json.dumps(ignition)


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
    extra_tls_sans: list[str] | None = None,
    needs_external_cloud_provider: bool = False,
    os_type: str = OS_TYPE_UBUNTU,
    server_node_name: str | None = None,
    # 하위호환 파라미터 (deprecated — 레지스트리 우회 시에만 사용)
    occm_enabled: bool = False,
    occm_manifests: str | None = None,
) -> UserdataResult:
    """k3s 서버 노드 userdata를 렌더링하여 UserdataResult 반환.

    Ubuntu: cloud-init YAML → gzip+base64 인코딩, config_drive=False
    FCOS  : Ignition JSON → raw (gzip 안 함), config_drive=True

    신규 호출자는 plugin_manifests / extra_server_args / cloud_conf를 직접 전달할 것.
    occm_enabled + occm_manifests는 하위호환용으로만 유지.
    """
    # 하위호환: 구 occm_enabled 파라미터 지원
    if occm_enabled and occm_manifests and not plugin_manifests:
        plugin_manifests = [{"name": "occm", "content": occm_manifests}]
        needs_external_cloud_provider = True

    if os_type == OS_TYPE_FCOS:
        ign_str = _build_server_ignition(
            cluster_name=cluster_name,
            k3s_version=k3s_version,
            callback_url=callback_url,
            callback_token=callback_token,
            cloud_conf=cloud_conf or "",
            plugins=plugin_manifests or [],
            extra_server_args=extra_server_args or [],
            extra_write_files=extra_write_files or [],
            extra_tls_sans=extra_tls_sans or [],
            needs_external_cloud_provider=needs_external_cloud_provider,
            server_node_name=server_node_name or "",
        )
        # Ignition JSON 유효성 간단 확인
        json.loads(ign_str)
        # Nova API는 user_data를 base64 디코딩 후 config drive에 기록.
        # raw JSON을 그대로 보내면 base64 디코딩 시 바이너리 garbage가 되므로
        # 반드시 base64 인코딩하여 전달해야 한다.
        encoded = base64.b64encode(ign_str.encode()).decode()
        return UserdataResult(data=encoded, config_drive=True)

    # Ubuntu (기본)
    template_vars = dict(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        callback_url=callback_url,
        callback_token=callback_token,
        cloud_conf=cloud_conf or "",
        plugins=plugin_manifests or [],
        extra_server_args=extra_server_args or [],
        extra_write_files=extra_write_files or [],
        extra_tls_sans=extra_tls_sans or [],
        needs_external_cloud_provider=needs_external_cloud_provider,
        server_node_name=server_node_name or f"{cluster_name}-server",
    )
    yaml_str = _jinja.get_template("k3s_server.yaml.j2").render(**template_vars)
    encoded = base64.b64encode(gzip.compress(yaml_str.encode())).decode()
    return UserdataResult(data=encoded, config_drive=False)


def generate_agent_userdata(
    cluster_name: str,
    k3s_version: str,
    server_ip: str,
    node_token: str,
    ssh_public_key: str | None = None,
    *,
    extra_agent_args: list[str] | None = None,
    os_type: str = OS_TYPE_UBUNTU,
    # 하위호환 파라미터 (deprecated)
    occm_enabled: bool = False,
) -> UserdataResult:
    """k3s 에이전트 노드 userdata를 렌더링하여 UserdataResult 반환."""
    if not node_token:
        raise ValueError("node_token이 비어있습니다. 서버 콜백에서 토큰이 전달되지 않았습니다.")

    # SSH 공개키 형식 검증 (YAML injection 방지)
    if ssh_public_key:
        _validate_ssh_public_key(ssh_public_key)

    # 하위호환: occm_enabled → cloud-provider=external
    agent_args = list(extra_agent_args or [])
    if occm_enabled and "--kubelet-arg=cloud-provider=external" not in agent_args:
        agent_args.append("--kubelet-arg=cloud-provider=external")

    if os_type == OS_TYPE_FCOS:
        ign_str = _build_agent_ignition(
            cluster_name=cluster_name,
            k3s_version=k3s_version,
            server_ip=server_ip,
            node_token=node_token,
            ssh_public_key=ssh_public_key or "",
            extra_agent_args=agent_args,
        )
        json.loads(ign_str)
        encoded = base64.b64encode(ign_str.encode()).decode()
        return UserdataResult(data=encoded, config_drive=True)

    # Ubuntu (기본)
    template_vars = dict(
        cluster_name=cluster_name,
        k3s_version=k3s_version,
        server_ip=server_ip,
        node_token=node_token,
        ssh_public_key=ssh_public_key or "",
        extra_agent_args=agent_args,
    )
    yaml_str = _jinja.get_template("k3s_agent.yaml.j2").render(**template_vars)
    return UserdataResult(data=base64.b64encode(gzip.compress(yaml_str.encode())).decode(), config_drive=False)
