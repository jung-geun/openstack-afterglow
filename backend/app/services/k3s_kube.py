"""K8s API 직접 호출 유틸리티.

kubeconfig의 클라이언트 인증서를 사용해 K8s API 서버에 직접 요청.
노드 삭제 등 클러스터 관리 작업에 사용.
"""

import base64
import contextlib
import logging
import ssl
import tempfile

import httpx
import yaml
from fastapi import HTTPException

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


# ---------------------------------------------------------------------------
# K8s API 공통 클라이언트 + 헬퍼
# ---------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def _kube_client(cluster_id: str, *, project_id: str | None = None):
    """K8s API 클라이언트 컨텍스트 매니저.

    project_id 가 주어지면 멀티테넌시 격리를 위해 `get_kubeconfig` 사용,
    없으면 관리자/내부 작업용 `get_kubeconfig_admin` 사용.
    """
    if project_id is not None:
        kubeconfig_yaml = await k3s_db.get_kubeconfig(project_id=project_id, cluster_id=cluster_id)
    else:
        kubeconfig_yaml = await k3s_db.get_kubeconfig_admin(cluster_id)
    if not kubeconfig_yaml:
        raise HTTPException(status_code=502, detail="kubeconfig 를 찾을 수 없습니다 (클러스터 미준비)")
    cert_pem, key_pem, server_url = _parse_kubeconfig(kubeconfig_yaml)
    ssl_ctx = _make_ssl_context(cert_pem, key_pem)
    async with httpx.AsyncClient(verify=ssl_ctx, timeout=15.0) as client:
        yield client, server_url


def _raise_k8s_error(resp: httpx.Response, context: str) -> None:
    """K8s API 비정상 응답을 HTTPException(502) 으로 정규화."""
    try:
        body = resp.json()
        detail = body.get("message") or body.get("reason") or resp.text
    except Exception:
        detail = resp.text[:500]
    _logger.warning("k3s_kube: %s 실패 (status=%d): %s", context, resp.status_code, detail)
    raise HTTPException(status_code=502, detail=f"K8s API {context} 실패: {detail}")


def _cm_from_k8s(item: dict) -> dict:
    meta = item.get("metadata", {})
    return {
        "name": meta.get("name", ""),
        "namespace": meta.get("namespace", ""),
        "data": item.get("data") or {},
        "binary_data": item.get("binaryData"),
        "labels": meta.get("labels") or {},
        "annotations": meta.get("annotations") or {},
        "created_at": meta.get("creationTimestamp", "") or "",
    }


def _secret_from_k8s(item: dict) -> dict:
    meta = item.get("metadata", {})
    return {
        "name": meta.get("name", ""),
        "namespace": meta.get("namespace", ""),
        "type": item.get("type", "Opaque"),
        "data": item.get("data") or {},
        "labels": meta.get("labels") or {},
        "annotations": meta.get("annotations") or {},
        "created_at": meta.get("creationTimestamp", "") or "",
    }


# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------


async def list_namespaces(cluster_id: str, *, project_id: str) -> list[str]:
    """클러스터의 네임스페이스 이름 목록."""
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.get(f"{server_url}/api/v1/namespaces", headers={"Accept": "application/json"})
        if resp.status_code != 200:
            _raise_k8s_error(resp, "namespace 목록 조회")
        items = resp.json().get("items", [])
        return [it.get("metadata", {}).get("name", "") for it in items if it.get("metadata", {}).get("name")]


# ---------------------------------------------------------------------------
# ConfigMap
# ---------------------------------------------------------------------------


async def list_configmaps(cluster_id: str, namespace: str, *, project_id: str) -> list[dict]:
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.get(
            f"{server_url}/api/v1/namespaces/{namespace}/configmaps",
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            _raise_k8s_error(resp, "ConfigMap 목록 조회")
        return [_cm_from_k8s(it) for it in resp.json().get("items", [])]


async def get_configmap(cluster_id: str, namespace: str, name: str, *, project_id: str) -> dict:
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.get(
            f"{server_url}/api/v1/namespaces/{namespace}/configmaps/{name}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"ConfigMap {namespace}/{name} 을 찾을 수 없습니다")
        if resp.status_code != 200:
            _raise_k8s_error(resp, f"ConfigMap {namespace}/{name} 조회")
        return _cm_from_k8s(resp.json())


async def create_configmap(
    cluster_id: str,
    namespace: str,
    name: str,
    data: dict[str, str],
    *,
    labels: dict | None = None,
    annotations: dict | None = None,
    project_id: str,
) -> dict:
    body = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels or {},
            "annotations": annotations or {},
        },
        "data": data or {},
    }
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.post(
            f"{server_url}/api/v1/namespaces/{namespace}/configmaps",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if resp.status_code not in (200, 201):
            _raise_k8s_error(resp, f"ConfigMap {namespace}/{name} 생성")
        return _cm_from_k8s(resp.json())


async def update_configmap(
    cluster_id: str,
    namespace: str,
    name: str,
    data: dict[str, str],
    *,
    labels: dict | None = None,
    annotations: dict | None = None,
    project_id: str,
) -> dict:
    body = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels or {},
            "annotations": annotations or {},
        },
        "data": data or {},
    }
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.put(
            f"{server_url}/api/v1/namespaces/{namespace}/configmaps/{name}",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"ConfigMap {namespace}/{name} 을 찾을 수 없습니다")
        if resp.status_code != 200:
            _raise_k8s_error(resp, f"ConfigMap {namespace}/{name} 업데이트")
        return _cm_from_k8s(resp.json())


async def delete_configmap(cluster_id: str, namespace: str, name: str, *, project_id: str) -> None:
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.delete(
            f"{server_url}/api/v1/namespaces/{namespace}/configmaps/{name}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            return  # 이미 없음 — idempotent 처리
        if resp.status_code not in (200, 202):
            _raise_k8s_error(resp, f"ConfigMap {namespace}/{name} 삭제")


# ---------------------------------------------------------------------------
# Secret
# ---------------------------------------------------------------------------


def _encode_secret_data(data: dict[str, str]) -> dict[str, str]:
    """Secret data 값을 base64 인코딩 (K8s API 가 요구하는 형식)."""
    return {k: base64.b64encode(v.encode()).decode() for k, v in (data or {}).items()}


async def list_secrets(cluster_id: str, namespace: str, *, project_id: str) -> list[dict]:
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.get(
            f"{server_url}/api/v1/namespaces/{namespace}/secrets",
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            _raise_k8s_error(resp, "Secret 목록 조회")
        return [_secret_from_k8s(it) for it in resp.json().get("items", [])]


async def get_secret(cluster_id: str, namespace: str, name: str, *, project_id: str) -> dict:
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.get(
            f"{server_url}/api/v1/namespaces/{namespace}/secrets/{name}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Secret {namespace}/{name} 을 찾을 수 없습니다")
        if resp.status_code != 200:
            _raise_k8s_error(resp, f"Secret {namespace}/{name} 조회")
        return _secret_from_k8s(resp.json())


async def create_secret(
    cluster_id: str,
    namespace: str,
    name: str,
    data: dict[str, str],
    *,
    secret_type: str = "Opaque",
    labels: dict | None = None,
    annotations: dict | None = None,
    project_id: str,
) -> dict:
    body = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": secret_type,
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels or {},
            "annotations": annotations or {},
        },
        "data": _encode_secret_data(data),
    }
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.post(
            f"{server_url}/api/v1/namespaces/{namespace}/secrets",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if resp.status_code not in (200, 201):
            _raise_k8s_error(resp, f"Secret {namespace}/{name} 생성")
        return _secret_from_k8s(resp.json())


async def update_secret(
    cluster_id: str,
    namespace: str,
    name: str,
    data: dict[str, str],
    *,
    secret_type: str = "Opaque",
    labels: dict | None = None,
    annotations: dict | None = None,
    project_id: str,
) -> dict:
    body = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": secret_type,
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels or {},
            "annotations": annotations or {},
        },
        "data": _encode_secret_data(data),
    }
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.put(
            f"{server_url}/api/v1/namespaces/{namespace}/secrets/{name}",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Secret {namespace}/{name} 을 찾을 수 없습니다")
        if resp.status_code != 200:
            _raise_k8s_error(resp, f"Secret {namespace}/{name} 업데이트")
        return _secret_from_k8s(resp.json())


async def delete_secret(cluster_id: str, namespace: str, name: str, *, project_id: str) -> None:
    async with _kube_client(cluster_id, project_id=project_id) as (client, server_url):
        resp = await client.delete(
            f"{server_url}/api/v1/namespaces/{namespace}/secrets/{name}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            return
        if resp.status_code not in (200, 202):
            _raise_k8s_error(resp, f"Secret {namespace}/{name} 삭제")
