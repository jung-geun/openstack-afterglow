"""k3s_kube.py 유닛 테스트 — K8s API 노드 삭제."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 픽스처 / 헬퍼
# ---------------------------------------------------------------------------

_FAKE_KUBECONFIG = """
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: dGVzdA==
    server: https://10.0.0.1:6443
  name: test-cluster
contexts:
- context:
    cluster: test-cluster
    user: default
  name: default
current-context: default
kind: Config
users:
- name: default
  user:
    client-certificate-data: dGVzdA==
    client-key-data: dGVzdA==
"""


def _make_response(status_code: int):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = ""
    return resp


# ---------------------------------------------------------------------------
# _parse_kubeconfig 테스트
# ---------------------------------------------------------------------------


def test_parse_kubeconfig_returns_server_url():
    from app.services.k3s_kube import _parse_kubeconfig

    cert, key, url = _parse_kubeconfig(_FAKE_KUBECONFIG)
    assert url == "https://10.0.0.1:6443"
    assert isinstance(cert, bytes)
    assert isinstance(key, bytes)


# ---------------------------------------------------------------------------
# delete_k8s_node 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_k8s_node_no_kubeconfig():
    """kubeconfig 없을 때 False 반환."""
    with patch("app.services.k3s_kube.k3s_db") as mock_db:
        mock_db.get_kubeconfig_admin = AsyncMock(return_value=None)
        from app.services.k3s_kube import delete_k8s_node

        result = await delete_k8s_node("cluster-1", "test-node")
    assert result is False


@pytest.mark.asyncio
async def test_delete_k8s_node_success():
    """K8s API 200 응답 시 True 반환."""
    with patch("app.services.k3s_kube.k3s_db") as mock_db:
        mock_db.get_kubeconfig_admin = AsyncMock(return_value=_FAKE_KUBECONFIG)
        with patch("app.services.k3s_kube._parse_kubeconfig") as mock_parse:
            mock_parse.return_value = (b"cert", b"key", "https://10.0.0.1:6443")
            with patch("app.services.k3s_kube._make_ssl_context") as mock_ssl:
                mock_ssl.return_value = MagicMock()
                mock_client = AsyncMock()
                mock_client.delete = AsyncMock(return_value=_make_response(200))
                with patch("app.services.k3s_kube.httpx.AsyncClient") as mock_cls:
                    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    from app.services.k3s_kube import delete_k8s_node

                    result = await delete_k8s_node("cluster-1", "test-node")
    assert result is True


@pytest.mark.asyncio
async def test_delete_k8s_node_already_gone():
    """K8s API 404 응답 시에도 True 반환 (이미 삭제된 노드)."""
    with patch("app.services.k3s_kube.k3s_db") as mock_db:
        mock_db.get_kubeconfig_admin = AsyncMock(return_value=_FAKE_KUBECONFIG)
        with patch("app.services.k3s_kube._parse_kubeconfig") as mock_parse:
            mock_parse.return_value = (b"cert", b"key", "https://10.0.0.1:6443")
            with patch("app.services.k3s_kube._make_ssl_context") as mock_ssl:
                mock_ssl.return_value = MagicMock()
                mock_client = AsyncMock()
                mock_client.delete = AsyncMock(return_value=_make_response(404))
                with patch("app.services.k3s_kube.httpx.AsyncClient") as mock_cls:
                    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    from app.services.k3s_kube import delete_k8s_node

                    result = await delete_k8s_node("cluster-1", "test-node")
    assert result is True


@pytest.mark.asyncio
async def test_delete_k8s_node_api_error():
    """K8s API 500 응답 시 False 반환."""
    with patch("app.services.k3s_kube.k3s_db") as mock_db:
        mock_db.get_kubeconfig_admin = AsyncMock(return_value=_FAKE_KUBECONFIG)
        with patch("app.services.k3s_kube._parse_kubeconfig") as mock_parse:
            mock_parse.return_value = (b"cert", b"key", "https://10.0.0.1:6443")
            with patch("app.services.k3s_kube._make_ssl_context") as mock_ssl:
                mock_ssl.return_value = MagicMock()
                mock_client = AsyncMock()
                mock_client.delete = AsyncMock(return_value=_make_response(500))
                with patch("app.services.k3s_kube.httpx.AsyncClient") as mock_cls:
                    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    from app.services.k3s_kube import delete_k8s_node

                    result = await delete_k8s_node("cluster-1", "test-node")
    assert result is False


@pytest.mark.asyncio
async def test_delete_k8s_node_connection_error():
    """연결 오류 시 False 반환 (예외 전파 안 됨)."""
    with patch("app.services.k3s_kube.k3s_db") as mock_db:
        mock_db.get_kubeconfig_admin = AsyncMock(return_value=_FAKE_KUBECONFIG)
        with patch("app.services.k3s_kube._parse_kubeconfig") as mock_parse:
            mock_parse.return_value = (b"cert", b"key", "https://10.0.0.1:6443")
            with patch("app.services.k3s_kube._make_ssl_context") as mock_ssl:
                mock_ssl.return_value = MagicMock()
                mock_client = AsyncMock()
                mock_client.delete = AsyncMock(side_effect=Exception("Connection refused"))
                with patch("app.services.k3s_kube.httpx.AsyncClient") as mock_cls:
                    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    from app.services.k3s_kube import delete_k8s_node

                    result = await delete_k8s_node("cluster-1", "test-node")
    assert result is False


@pytest.mark.asyncio
async def test_delete_k8s_nodes_calls_each():
    """delete_k8s_nodes는 각 노드에 delete_k8s_node를 호출한다."""
    with patch("app.services.k3s_kube.delete_k8s_node", new_callable=AsyncMock) as mock_del:
        mock_del.return_value = True
        from app.services.k3s_kube import delete_k8s_nodes

        await delete_k8s_nodes("cluster-1", ["node-a", "node-b", "node-c"])

    assert mock_del.call_count == 3
    called_names = [call.args[1] for call in mock_del.call_args_list]
    assert called_names == ["node-a", "node-b", "node-c"]


@pytest.mark.asyncio
async def test_delete_k8s_nodes_continues_on_failure():
    """일부 노드 삭제 실패해도 나머지 계속 진행한다."""
    results = [False, True, False]
    call_count = 0

    async def mock_delete(cluster_id, node_name):
        nonlocal call_count
        result = results[call_count]
        call_count += 1
        return result

    with patch("app.services.k3s_kube.delete_k8s_node", side_effect=mock_delete):
        from app.services.k3s_kube import delete_k8s_nodes

        await delete_k8s_nodes("cluster-1", ["node-a", "node-b", "node-c"])

    assert call_count == 3
