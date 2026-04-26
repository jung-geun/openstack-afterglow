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
        "server_vm_name": "mycluster-server",
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


@pytest.mark.asyncio
async def test_delete_k3s_cluster_vm_already_deleted(client):
    """VM이 이미 삭제된 상태(delete_server 404)여도 soft-delete까지 정상 완료해야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = False

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(return_value={})
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            # delete_server가 이미 없는 VM → 예외 없이 리턴 (nova.py에서 404 처리)
            mock_nova.delete_server = MagicMock()
            mock_nova.wait_server_deleted = MagicMock()
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                    mock_kube.delete_k8s_nodes = AsyncMock()
                    resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    mock_db.delete_cluster_record.assert_called_once()


@pytest.mark.asyncio
async def test_delete_k3s_cluster_vm_wait_timeout(client):
    """VM 삭제 대기 타임아웃이 발생해도 SG 삭제와 soft-delete는 계속 진행해야 한다."""
    cluster = _make_cluster_record()
    cluster["occm_enabled"] = False
    cluster["security_group_id"] = "sg-1"

    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        mock_db.delete_cluster_record = AsyncMock()
        mock_db.get_agent_vm_names = AsyncMock(return_value={})
        with patch("app.api.k3s.clusters.nova") as mock_nova:
            mock_nova.delete_server = MagicMock()
            mock_nova.wait_server_deleted = MagicMock(side_effect=TimeoutError("timeout"))
            with patch("app.api.k3s.clusters.neutron") as mock_neutron:
                mock_neutron.delete_security_group = MagicMock()
                with patch("app.api.k3s.clusters.k3s_kube") as mock_kube:
                    mock_kube.delete_k8s_nodes = AsyncMock()
                    resp = await client.delete("/api/k3s/clusters/k3s-1")

    assert resp.status_code == 204
    mock_db.delete_cluster_record.assert_called_once()
    mock_neutron.delete_security_group.assert_called()


# ---------------------------------------------------------------------------
# API LB octavia 서비스 단위 테스트 (LB-first 전략)
# ---------------------------------------------------------------------------


def test_octavia_create_lb_with_subnet():
    """vip_subnet_id로 LB 생성 시 vip_subnet_id가 API 호출에 전달되어야 한다."""
    from app.services import octavia

    mock_conn = MagicMock()
    mock_lb = MagicMock()
    mock_lb.id = "lb-1"
    mock_lb.name = "test-lb"
    mock_lb.description = ""
    mock_lb.provisioning_status = "ACTIVE"
    mock_lb.operating_status = "ONLINE"
    mock_lb.vip_address = "192.168.1.100"
    mock_lb.vip_subnet_id = "subnet-1"
    mock_lb.vip_network_id = "net-1"
    mock_lb.vip_port_id = "port-1"
    mock_lb.project_id = "proj-1"
    mock_conn.load_balancer.create_load_balancer.return_value = mock_lb

    result = octavia.create_load_balancer(mock_conn, "test-lb", "subnet-1", "desc")

    mock_conn.load_balancer.create_load_balancer.assert_called_once_with(
        name="test-lb", description="desc", vip_subnet_id="subnet-1"
    )
    assert result["id"] == "lb-1"


def test_octavia_create_lb_with_vip_network_id():
    """vip_network_id 설정 시 vip_subnet_id 대신 vip_network_id가 API 호출에 전달되어야 한다."""
    from app.services import octavia

    mock_conn = MagicMock()
    mock_lb = MagicMock()
    mock_lb.id = "lb-2"
    mock_lb.name = "provider-lb"
    mock_lb.description = ""
    mock_lb.provisioning_status = "ACTIVE"
    mock_lb.operating_status = "ONLINE"
    mock_lb.vip_address = "10.100.0.50"
    mock_lb.vip_subnet_id = None
    mock_lb.vip_network_id = "provider-net-1"
    mock_lb.vip_port_id = "port-2"
    mock_lb.project_id = "proj-1"
    mock_conn.load_balancer.create_load_balancer.return_value = mock_lb

    result = octavia.create_load_balancer(
        mock_conn, "provider-lb", description="provider VIP LB", vip_network_id="provider-net-1"
    )

    call_kwargs = mock_conn.load_balancer.create_load_balancer.call_args[1]
    assert "vip_network_id" in call_kwargs
    assert call_kwargs["vip_network_id"] == "provider-net-1"
    assert "vip_subnet_id" not in call_kwargs
    assert result["id"] == "lb-2"


@pytest.mark.asyncio
async def test_finalize_api_lb_adds_member_and_health_monitor():
    """_finalize_api_lb는 member 추가 + health monitor만 수행해야 한다 (listener/pool 생성 없음)."""
    from app.api.k3s.callback import _finalize_api_lb

    cluster = {
        "id": "cluster-1",
        "name": "mycluster",
        "api_lb_id": "lb-1",
        "api_lb_pool_id": "pool-1",
        "api_fip_id": "",  # provider VIP 모드: FIP 없음
        "api_fip_address": "10.100.0.50",
        "network_id": "net-1",
    }

    mock_conn = MagicMock()

    with (
        patch("app.services.k3s_db.update_cluster_status", new_callable=AsyncMock),
        patch(
            "app.services.k3s_db.get_kubeconfig", new_callable=AsyncMock, return_value="server: https://10.0.0.1:6443"
        ),
        patch("app.services.k3s_db.store_kubeconfig", new_callable=AsyncMock) as mock_store_kube,
        patch("app.services.octavia") as mock_octavia,
    ):
        mock_lb = {"vip_subnet_id": "subnet-provider", "vip_port_id": "port-1", "vip_address": "10.100.0.50"}
        mock_octavia.wait_for_load_balancer = MagicMock(return_value=mock_lb)
        mock_octavia.add_member = MagicMock()
        mock_octavia.create_health_monitor = MagicMock()
        mock_octavia.get_load_balancer = MagicMock(return_value=mock_lb)

        mock_net = MagicMock()
        mock_net.subnet_ids = ["subnet-tenant"]
        mock_conn.network.get_network = MagicMock(return_value=mock_net)

        await _finalize_api_lb("proj-1", "cluster-1", cluster, "10.0.0.1", mock_conn)

    # member 추가 호출
    mock_octavia.add_member.assert_called_once()
    call_args = mock_octavia.add_member.call_args
    assert call_args[0][1] == "pool-1"  # pool_id
    assert call_args[0][2] == "10.0.0.1"  # server_ip
    assert call_args[0][3] == 6443  # port
    # health monitor 생성 호출
    mock_octavia.create_health_monitor.assert_called_once()
    # kubeconfig 패치 확인
    mock_store_kube.assert_called_once()
    patched_kubeconfig = mock_store_kube.call_args[0][2]
    assert "10.100.0.50" in patched_kubeconfig


@pytest.mark.asyncio
async def test_finalize_api_lb_skips_when_no_pool_id():
    """api_lb_pool_id가 없으면 _finalize_api_lb는 아무 작업도 하지 않아야 한다."""
    from app.api.k3s.callback import _finalize_api_lb

    cluster = {
        "id": "cluster-1",
        "name": "mycluster",
        "api_lb_id": "lb-1",
        "api_lb_pool_id": "",  # pool ID 없음
        "api_fip_id": "",
        "api_fip_address": "10.100.0.50",
        "network_id": "net-1",
    }

    mock_conn = MagicMock()
    with patch("app.services.octavia") as mock_octavia:
        await _finalize_api_lb("proj-1", "cluster-1", cluster, "10.0.0.1", mock_conn)
        mock_octavia.wait_for_load_balancer.assert_not_called()
        mock_octavia.add_member.assert_not_called()
