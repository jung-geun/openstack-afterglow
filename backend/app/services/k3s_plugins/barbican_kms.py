"""Barbican KMS Plugin — K8s Secret을 Barbican으로 암호화.

8.14 데드락 해소 — host static pod 방식.

기존엔 DaemonSet으로 KMS 데몬을 띄웠으나, 이는 apiserver 위에서 동작하므로
부팅 시점 apiserver의 ``--encryption-provider-config`` 초기화와 chicken-and-egg
데드락이 발생했다. 본 재설계는 kubelet이 apiserver 없이도 띄울 수 있는
**host static pod**(`/var/lib/rancher/k3s/agent/pod-manifests/`)로 KMS 데몬을
배포한다. KMS 소켓이 host에서 즉시 생성되어 apiserver의 KMS provider
초기화 retry(`PluginInitTimeout`, 기본 60초)를 충족한다.
"""

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

_STATIC_POD_DIR = "/var/lib/rancher/k3s/agent/pod-manifests"


class BarbicanKmsPlugin:
    name = "barbican_kms"

    def should_deploy(self, settings: Settings) -> bool:
        if not settings.k3s_barbican_kms_enabled:
            return False
        if not settings.k3s_barbican_kms_kek_id:
            _logger.warning("Barbican KMS 활성화됨이지만 KEK ID 미설정")
            return False
        if not settings.os_username or not settings.os_password:
            _logger.warning("Barbican KMS 활성화됨이지만 OpenStack 인증 정보 미설정")
            return False
        return True

    def cloud_conf_sections(self, project_id: str, settings: Settings) -> str:
        """OCCM의 cluster cloud.conf에 추가될 [KeyManager] 섹션 반환.

        주의: 이 섹션은 **OCCM이 사용하는 cluster cloud.conf**에 추가되는 것이며,
        KMS static pod가 사용하는 host file `/etc/kubernetes/barbican-cloud.conf` 와는
        별개다 (KMS는 apiserver에 secret으로 접근할 수 없으므로 host file 필요).
        """
        return "[KeyManager]\nuse-barbican=true\n"

    def generate_manifests(self, cluster_name: str, project_id: str, settings: Settings, **kwargs) -> str:
        """Static pod로 전환되어 K8s 매니페스트 배포 불필요. 빈 문자열 반환."""
        return ""

    def extra_write_files(self, project_id: str, cluster_name: str, settings: Settings) -> list[dict]:
        """Static pod 운영에 필요한 host file 3건 작성.

        1. encryption-config.yaml — apiserver가 부팅 시 읽음
        2. static pod manifest — kubelet이 감시 → KMS pod 즉시 띄움
        3. barbican-cloud.conf — KMS pod가 hostPath로 읽음 (Secret 의존 제거)
        """
        encryption_config = _jinja.get_template("k3s_plugins/barbican_kms/encryption_config.yaml.j2").render()
        static_pod = _jinja.get_template("k3s_plugins/barbican_kms/static_pod.yaml.j2").render(
            barbican_kms_image=settings.k3s_barbican_kms_image,
            kek_id=settings.k3s_barbican_kms_kek_id,
        )
        cloud_conf = _jinja.get_template("k3s_plugins/barbican_kms/cloud_conf.yaml.j2").render(
            auth_url=settings.os_auth_url,
            region=settings.os_region_name,
            username=settings.os_username,
            password=settings.os_password,
            user_domain_name=settings.os_user_domain_name,
            project_name=settings.os_project_name,
            project_domain_name=getattr(settings, "os_project_domain_name", "") or "",
            ca_file="" if settings.os_insecure else (settings.os_cacert or ""),
        )
        return [
            {
                "path": "/etc/kubernetes/encryption-config.yaml",
                "permissions": "0600",
                "content": encryption_config,
            },
            {
                "path": f"{_STATIC_POD_DIR}/barbican-kms.yaml",
                "permissions": "0600",
                "content": static_pod,
            },
            {
                "path": "/etc/kubernetes/barbican-cloud.conf",
                "permissions": "0600",
                "content": cloud_conf,
            },
        ]

    def server_install_args(self, settings: Settings) -> list[str]:
        return [
            "--kube-apiserver-arg=encryption-provider-config=/etc/kubernetes/encryption-config.yaml",
            f"--kubelet-arg=pod-manifest-path={_STATIC_POD_DIR}",
        ]

    def agent_install_args(self, settings: Settings) -> list[str]:
        return []

    def needs_external_cloud_provider(self, settings: Settings) -> bool:
        return False
