"""K8s API 직접 호출 유틸리티.

kubeconfig의 클라이언트 인증서를 사용해 K8s API 서버에 직접 요청.
노드 삭제 등 클러스터 관리 작업에 사용.
"""

import base64
import logging
import ssl
import tempfile

import httpx
import yaml

from app.services import k3s_db

_logger = logging.getLogger(__name__)


def _parse_kubeconfig(kubeconfig_yaml: str) -> tuple[bytes, bytes, str]:
    """kubeconfig에서 (client_cert_pem, client_key_pem, server_url) 반환."""
    kc = yaml.safe_load(kubeconfig_yaml)
    user = kc["users"][0]["user"]
    cert_data = base64.b64decode(user["client-certificate-data"])
    key_data = base64.b64decode(user["client-key-data"])
    server_url = kc["clusters"][0]["cluster"]["server"]
    return cert_data, key_data, server_url


def _make_ssl_context(cert_pem: bytes, key_pem: bytes) -> ssl.SSLContext:
    """클라이언트 인증서로 SSLContext 생성 (K3s 자체 서명 인증서 허용)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with (
        tempfile.NamedTemporaryFile(suffix=".crt") as cf,
        tempfile.NamedTemporaryFile(suffix=".key") as kf,
    ):
        cf.write(cert_pem)
        cf.flush()
        kf.write(key_pem)
        kf.flush()
        ctx.load_cert_chain(cf.name, kf.name)
    return ctx


async def delete_k8s_node(cluster_id: str, node_name: str) -> bool:
    """K8s API로 노드 삭제.

    Returns:
        True — 성공 또는 이미 없음(404)
        False — 오류 발생 (kubeconfig 없음, 연결 실패 등)
    """
    try:
        kubeconfig_yaml = await k3s_db.get_kubeconfig_admin(cluster_id)
        if not kubeconfig_yaml:
            _logger.warning("k3s_kube: kubeconfig 없음 (cluster=%s), 노드 삭제 스킵: %s", cluster_id, node_name)
            return False

        cert_pem, key_pem, server_url = _parse_kubeconfig(kubeconfig_yaml)
        ssl_ctx = _make_ssl_context(cert_pem, key_pem)

        async with httpx.AsyncClient(verify=ssl_ctx, timeout=10.0) as client:
            resp = await client.delete(
                f"{server_url}/api/v1/nodes/{node_name}",
                headers={"Accept": "application/json"},
            )
            if resp.status_code in (200, 404):
                _logger.info("k3s_kube: node %s 삭제 완료 (status=%d)", node_name, resp.status_code)
                return True
            _logger.warning(
                "k3s_kube: node %s 삭제 실패: HTTP %d %s",
                node_name,
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as e:
        _logger.warning("k3s_kube: node %s 삭제 중 오류: %s", node_name, e)
        return False


async def delete_k8s_nodes(cluster_id: str, node_names: list[str]) -> None:
    """여러 노드 순차 삭제 (best-effort — 실패해도 계속 진행)."""
    for name in node_names:
        await delete_k8s_node(cluster_id, name)
