"""Keystone Webhook Auth Plugin — K8s 인증을 OpenStack Keystone과 연동."""

import base64
import datetime
import ipaddress
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


def _generate_self_signed_cert() -> tuple[bytes, bytes]:
    """k8s-keystone-auth 서비스용 self-signed TLS 인증서 생성.

    Returns:
        (cert_pem, key_pem) — PEM 인코딩 인증서와 키
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        _logger.error("cryptography 패키지 필요: uv add cryptography")
        raise

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "k8s-keystone-auth"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "union-k3s"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("k8s-keystone-auth"),
                x509.DNSName("k8s-keystone-auth.kube-system"),
                x509.DNSName("k8s-keystone-auth.kube-system.svc"),
                x509.DNSName("k8s-keystone-auth.kube-system.svc.cluster.local"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


class KeystoneAuthPlugin:
    name = "keystone_auth"

    # 생성된 인증서를 캐싱 (동일 클러스터 내 server/agent 일관성)
    _cert_cache: dict[str, tuple[bytes, bytes]] = {}

    def should_deploy(self, settings: Settings) -> bool:
        if not settings.k3s_keystone_auth_enabled:
            return False
        if not settings.os_auth_url:
            _logger.warning("KeystoneAuth 활성화됨이지만 os_auth_url 미설정")
            return False
        return True

    def cloud_conf_sections(self, project_id: str, settings: Settings) -> str:
        return ""

    def _get_or_create_cert(self, cluster_name: str) -> tuple[bytes, bytes]:
        if cluster_name not in self._cert_cache:
            self._cert_cache[cluster_name] = _generate_self_signed_cert()
        return self._cert_cache[cluster_name]

    def generate_manifests(self, cluster_name: str, project_id: str, settings: Settings) -> str:
        cert_pem, key_pem = self._get_or_create_cert(cluster_name)
        cert_b64 = base64.b64encode(cert_pem).decode()
        key_b64 = base64.b64encode(key_pem).decode()
        return _jinja.get_template("k3s_plugins/keystone_auth/manifests.yaml.j2").render(
            keystone_auth_image=settings.k3s_keystone_auth_image,
            os_auth_url=settings.os_auth_url,
            cert_b64=cert_b64,
            key_b64=key_b64,
            policy=settings.k3s_keystone_auth_policy,
        )

    def extra_write_files(self, project_id: str, cluster_name: str, settings: Settings) -> list[dict]:
        """webhook config 파일을 /etc/kubernetes/에 작성."""
        cert_pem, _ = self._get_or_create_cert(cluster_name)
        cert_b64 = base64.b64encode(cert_pem).decode()
        webhook_config = _jinja.get_template("k3s_plugins/keystone_auth/webhook_config.yaml.j2").render(
            cert_b64=cert_b64,
        )
        return [
            {
                "path": "/etc/kubernetes/keystone-webhook.yaml",
                "permissions": "0600",
                "content": webhook_config,
            }
        ]

    def server_install_args(self, settings: Settings) -> list[str]:
        return [
            "--kube-apiserver-arg=authentication-token-webhook-config-file=/etc/kubernetes/keystone-webhook.yaml",
        ]

    def agent_install_args(self, settings: Settings) -> list[str]:
        return []

    def needs_external_cloud_provider(self, settings: Settings) -> bool:
        return False
