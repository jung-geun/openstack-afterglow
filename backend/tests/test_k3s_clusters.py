"""k3s/clusters.py 엔드포인트 단위 테스트 (6개, k3s 서비스 필요)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_cluster_record():
    return {
        "id": "k3s-1",
        "name": "mycluster",
        "status": "ACTIVE",
        "status_reason": None,
        "server_vm_id": "vm-1",
        "agent_vm_ids": [],
        "agent_count": 0,
        "api_address": None,
        "server_ip": "10.0.0.1",
        "network_id": "net-1",
        "key_name": None,
        "k3s_version": "v1.31.4+k3s1",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_list_k3s_clusters_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_k3s_clusters_success(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.list_clusters = AsyncMock(return_value=[_make_cluster_record()])
        resp = await client.get("/api/k3s/clusters")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_k3s_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters/k3s-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_k3s_cluster_success(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        resp = await client.get("/api/k3s/clusters/k3s-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_k3s_cluster_not_found(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=None)
        resp = await client.get("/api/k3s/clusters/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_kubeconfig_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_download_kubeconfig_not_ready(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        mock_db.get_kubeconfig = AsyncMock(return_value=None)
        resp = await client.get("/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_kubeconfig_success(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        mock_db.get_kubeconfig = AsyncMock(return_value=b"apiVersion: v1\n...")
        resp = await client.get("/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_head_kubeconfig_ready(client):
    """kubeconfig 준비된 경우 HEAD 요청이 200을 반환해야 한다."""
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        mock_db.get_kubeconfig = AsyncMock(return_value=b"apiVersion: v1\n...")
        resp = await client.request("HEAD", "/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 200
    assert resp.content == b""  # HEAD는 body 없어야 함


@pytest.mark.asyncio
async def test_head_kubeconfig_not_ready(client):
    """kubeconfig 미준비 시 HEAD도 404를 반환해야 한다."""
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        mock_db.get_kubeconfig = AsyncMock(return_value=None)
        resp = await client.request("HEAD", "/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scale_k3s_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.patch("/api/k3s/clusters/k3s-1/scale", json={"agent_count": 2})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scale_k3s_cluster_success(client):
    cluster = _make_cluster_record()
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        with patch("app.api.k3s.clusters.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()
            resp = await client.patch("/api/k3s/clusters/k3s-1/scale", json={"agent_count": 0})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_k3s_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/k3s/clusters/k3s-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_k3s_cluster_not_found(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=None)
        resp = await client.delete("/api/k3s/clusters/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_k3s_cluster_cleans_occm_lbs(client):
    """OCCM 활성 클러스터 삭제 시 Octavia LB를 정리해야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = True

    mock_lbs = [
        {"id": "lb-1", "name": "kube_service_mycluster_kube-system_traefik"},
        {"id": "lb-2", "name": "kube_service_mycluster_default_my-svc"},
        {"id": "lb-3", "name": "other-lb-not-related"},
    ]

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(return_value={})
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            mock_nova.delete_server = MagicMock()
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.octavia") as mock_octavia:
                    mock_octavia.list_load_balancers = MagicMock(return_value=mock_lbs)
                    mock_octavia.delete_load_balancer = MagicMock()
                    with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                        mock_kube.delete_k8s_nodes = AsyncMock()
                        resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    # 클러스터 이름 prefix에 해당하는 LB 2개만 삭제되어야 함
    assert mock_octavia.delete_load_balancer.call_count == 2
    deleted_ids = {call.args[1] for call in mock_octavia.delete_load_balancer.call_args_list}
    assert deleted_ids == {"lb-1", "lb-2"}


@pytest.mark.asyncio
async def test_delete_k3s_cluster_lb_cleanup_failure_continues(client):
    """LB 정리 실패해도 클러스터 삭제는 계속 진행되어야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = True

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(return_value={})
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            mock_nova.delete_server = MagicMock()
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.octavia") as mock_octavia:
                    mock_octavia.list_load_balancers = MagicMock(side_effect=Exception("Octavia unavailable"))
                    with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                        mock_kube.delete_k8s_nodes = AsyncMock()
                        resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    mock_db.delete_cluster_record.assert_called_once()


@pytest.mark.asyncio
async def test_delete_k3s_cluster_no_occm_skips_lb_cleanup(client):
    """OCCM 비활성 클러스터는 LB 정리를 스킵해야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = False

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(return_value={})
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            mock_nova.delete_server = MagicMock()
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.octavia") as mock_octavia:
                    mock_octavia.list_load_balancers = MagicMock()
                    with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                        mock_kube.delete_k8s_nodes = AsyncMock()
                        resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    mock_octavia.list_load_balancers.assert_not_called()


@pytest.mark.asyncio
async def test_delete_k3s_cluster_deletes_k8s_nodes(client):
    """클러스터 삭제 시 agent 노드와 server 노드를 K8s API로 삭제해야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = False
    cluster["agent_vm_ids"] = ["vm-agent-1", "vm-agent-2"]

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(
            return_value={
                "vm-agent-1": "mycluster-agent-1",
                "vm-agent-2": "mycluster-agent-2",
            }
        )
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            mock_nova.delete_server = MagicMock()
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                    mock_kube.delete_k8s_nodes = AsyncMock()
                    resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    mock_kube.delete_k8s_nodes.assert_called_once()
    node_names = mock_kube.delete_k8s_nodes.call_args.args[1]
    assert "mycluster-agent-1" in node_names
    assert "mycluster-agent-2" in node_names
    assert "mycluster-server" in node_names


@pytest.mark.asyncio
async def test_delete_k3s_cluster_continues_if_k8s_node_delete_fails(client):
    """K8s 노드 삭제 실패해도 VM 삭제와 soft-delete는 계속 진행되어야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = False

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(return_value={})
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            mock_nova.delete_server = MagicMock()
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                    mock_kube.delete_k8s_nodes = AsyncMock(side_effect=Exception("K8s API unreachable"))
                    resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    mock_db.delete_cluster_record.assert_called_once()
