"""admin.py (GET/POST/PUT/PATCH/DELETE) 엔드포인트 단위 테스트.

각 엔드포인트에 대해:
  - non_admin_client  → 403 (require_admin 관문)
  - admin_client       → 403이 아님 (관문 통과)

admin_client 테스트는 응답 상태 코드가 403이 아닌 것만 검증한다.
OpenStack SDK는 mock_conn으로 대체되므로 404/500 등도 "통과" 로 간주.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 파일 스토리지 관련 (3개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_admin_file_storages_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/file-storage")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_admin_file_storages_allowed(admin_client, mock_conn):
    with patch("app.api.identity.admin.manila.list_file_storages", return_value=[]):
        resp = await admin_client.get("/api/admin/file-storage")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_trigger_build_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/file-storage/build?library_id=test")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_active_builds_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/file-storage/builds")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_active_builds_allowed(admin_client):
    with patch("app.api.identity.admin.library_builder") as m:
        m.list_active_builds = MagicMock(return_value=[])
        resp = await admin_client.get("/api/admin/file-storage/builds")
    assert resp.status_code != 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 개요 / 하이퍼바이저 (4개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_admin_overview_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/overview")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_overview_allowed(admin_client):
    with patch("app.api.identity.admin.cached_call") as mc:
        mc.side_effect = AsyncMock(
            return_value={
                "hypervisor_count": 0,
                "running_vms": 0,
                "gpu_instances": 0,
                "instance_stats": {},
                "vcpus": {"total": 0, "allowed": 0, "used": 0},
                "ram_gb": {"total": 0, "used": 0},
                "disk_gb": {"total": 0, "used": 0},
                "containers_count": 0,
                "file_storage_count": 0,
            }
        )
        resp = await admin_client.get("/api/admin/overview")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_list_hypervisors_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/hypervisors")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_hypervisors_allowed(admin_client):
    with patch("app.api.identity.admin.cached_call") as mc:
        mc.side_effect = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/admin/hypervisors")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_get_hypervisor_detail_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/hypervisors/hv-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_hypervisor_detail_allowed(admin_client, mock_conn):
    mock_conn.compute.get_hypervisor.return_value = MagicMock(
        id="hv-1",
        name="hv-1",
        status="enabled",
        state="up",
        host_ip="10.0.0.1",
        type="QEMU",
        vcpus=64,
        vcpus_used=0,
        memory_size=512000,
        memory_used=0,
        local_disk_size=5000,
        local_disk_used=0,
    )
    resp = await admin_client.get("/api/admin/hypervisors/hv-1")
    assert resp.status_code != 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 전체 리소스 조회 (6개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_all_instances_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-instances")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_instances_allowed(admin_client):
    with patch("app.api.identity.admin.cached_call") as mc:
        mc.side_effect = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/admin/all-instances")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_list_all_volumes_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-volumes")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_volumes_allowed(admin_client):
    with patch("app.api.identity.admin.cached_call") as mc:
        mc.side_effect = AsyncMock(return_value=[])
        resp = await admin_client.get("/api/admin/all-volumes")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_list_all_containers_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-containers")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_file_storages_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-file-storages")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_topology_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/topology")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_timeseries_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/timeseries/instances")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_networks_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-networks")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_floating_ips_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-floating-ips")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_routers_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-routers")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_all_ports_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/all-ports")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 포트 생성 (1개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_create_port_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/ports", json={"network_id": "net-1", "name": "test-port"})
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 할당량 / 프로젝트 개요
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_project_quota_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/quotas/proj-123")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_overview_projects_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/overview/projects")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 볼륨 관리 (5개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_admin_volume_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/volumes/vol-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_admin_volume_requires_admin(non_admin_client):
    resp = await non_admin_client.patch("/api/admin/volumes/vol-1", json={"name": "new"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_volume_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/volumes/vol-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_extend_admin_volume_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/volumes/vol-1/extend", json={"size": 100})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reset_volume_status_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/volumes/vol-1/reset-status", json={"status": "available"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_transfer_volume_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/volumes/vol-1/transfer", json={"project_id": "proj-2"})
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 컴퓨트 호스트 / 인스턴스 마이그레이션
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_compute_hosts_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/compute-hosts")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_live_migrate_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/instances/inst-1/live-migrate", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cold_migrate_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/instances/inst-1/cold-migrate", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_confirm_resize_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/instances/inst-1/confirm-resize")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 네트워크 관리 (4개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_admin_network_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/networks/net-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_admin_network_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/networks", json={"name": "net"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_admin_network_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/admin/networks/net-1", json={"name": "net"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_network_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/networks/net-1")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 플로팅 IP 관리 (2개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_create_admin_floating_ip_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/floating-ips", json={"floating_network_id": "net-1"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_floating_ip_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/floating-ips/fip-1")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 라우터 관리 (3개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_create_admin_router_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/routers", json={"name": "r"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_admin_router_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/admin/routers/router-1", json={"name": "r"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_router_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/routers/router-1")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 포트 관리 (2개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_update_admin_port_requires_admin(non_admin_client):
    resp = await non_admin_client.put("/api/admin/ports/port-1", json={"name": "p"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_port_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/ports/port-1")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# k3s 클러스터 관리 (4개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_list_k3s_clusters_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/k3s-clusters")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_admin_k3s_cluster_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/k3s-clusters/cluster-1")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_admin_kubeconfig_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/k3s-clusters/cluster-1/kubeconfig")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_admin_k3s_cluster_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/k3s-clusters/cluster-1")
    assert resp.status_code == 403


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 버전 (1개)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_get_version_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/version")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_version_allowed(admin_client):
    resp = await admin_client.get("/api/admin/version")
    assert resp.status_code != 403
