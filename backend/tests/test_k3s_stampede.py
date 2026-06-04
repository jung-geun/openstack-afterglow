"""Stampede 오토스케일 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


def _make_cluster(stampede_enabled=True):
    return {
        "id": "cl-1",
        "name": "testcluster",
        "status": "ACTIVE",
        "status_reason": None,
        "server_vm_id": "vm-server",
        "agent_vm_ids": [],
        "agent_count": 0,
        "server_ip": "10.0.0.1",
        "network_id": "net-1",
        "security_group_id": "sg-1",
        "key_name": None,
        "ssh_public_key": None,
        "k3s_version": "v1.31.4+k3s1",
        "os_type": "ubuntu",
        "agent_flavor_id": "fl-small",
        "occm_enabled": False,
        "stampede_enabled": stampede_enabled,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


def _make_nodegroup(stampede_enabled=True, node_count=0, min_size=1, max_size=3):
    return {
        "id": "ng-1",
        "cluster_id": "cl-1",
        "name": "auto-workers",
        "role": "agent",
        "node_count": node_count,
        "flavor_id": "fl-small",
        "image_id": None,
        "labels": {"env": "test"},
        "taints": [],
        "is_default": False,
        "stampede_enabled": stampede_enabled,
        "min_size": min_size,
        "max_size": max_size,
        "stampede_state": {},
        "vms": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# k3s_stampede 로직 단위 테스트
# ---------------------------------------------------------------------------


def test_node_matches_nodegroup_no_selector():
    """nodeSelector 없는 pod는 어느 nodegroup에나 매칭."""
    from app.services.k3s_stampede import _node_matches_nodegroup

    pod = {"node_selector": {}, "tolerations": []}
    ng = {"labels": {}, "taints": []}
    assert _node_matches_nodegroup(pod, ng) is True


def test_node_matches_nodegroup_selector_match():
    """nodeSelector가 nodegroup labels를 만족하면 매칭."""
    from app.services.k3s_stampede import _node_matches_nodegroup

    pod = {"node_selector": {"env": "test"}, "tolerations": []}
    ng = {"labels": {"env": "test", "zone": "a"}, "taints": []}
    assert _node_matches_nodegroup(pod, ng) is True


def test_node_matches_nodegroup_selector_no_match():
    """nodeSelector가 nodegroup labels와 불일치면 매칭 실패."""
    from app.services.k3s_stampede import _node_matches_nodegroup

    pod = {"node_selector": {"env": "prod"}, "tolerations": []}
    ng = {"labels": {"env": "test"}, "taints": []}
    assert _node_matches_nodegroup(pod, ng) is False


def test_node_matches_nodegroup_taint_no_toleration():
    """nodegroup에 NoSchedule taint 있고 pod에 toleration 없으면 매칭 실패."""
    from app.services.k3s_stampede import _node_matches_nodegroup

    pod = {"node_selector": {}, "tolerations": []}
    ng = {"labels": {}, "taints": [{"key": "dedicated", "value": "gpu", "effect": "NoSchedule"}]}
    assert _node_matches_nodegroup(pod, ng) is False


def test_node_matches_nodegroup_taint_with_toleration():
    """pod에 적절한 toleration이 있으면 taint 있어도 매칭."""
    from app.services.k3s_stampede import _node_matches_nodegroup

    pod = {
        "node_selector": {},
        "tolerations": [{"key": "dedicated", "operator": "Equal", "value": "gpu", "effect": "NoSchedule"}],
    }
    ng = {"labels": {}, "taints": [{"key": "dedicated", "value": "gpu", "effect": "NoSchedule"}]}
    assert _node_matches_nodegroup(pod, ng) is True


def test_is_pvc_issue_detected():
    """PVC 관련 메시지면 PVC 이슈로 판정."""
    from app.services.k3s_stampede import _is_pvc_issue

    pod = {"message": "0/3 nodes are available: pod has unbound immediate PersistentVolumeClaims"}
    assert _is_pvc_issue(pod) is True


def test_is_pvc_issue_not_pvc():
    """일반 리소스 부족은 PVC 이슈 아님."""
    from app.services.k3s_stampede import _is_pvc_issue

    pod = {"message": "Insufficient cpu"}
    assert _is_pvc_issue(pod) is False


def test_select_flavor_basic():
    """pending pod에 맞는 최소 flavor 선택."""
    from app.services.k3s_stampede import _select_flavor

    pending = [{"resource_requests": {"cpu_m": 500, "memory_bytes": 512 * 1024**2, "gpu": 0}}]
    flavors = [
        {"id": "small", "name": "m1.small", "vcpus_m": 1000, "ram_bytes": 1024**3, "gpu": 0},
        {"id": "large", "name": "m1.large", "vcpus_m": 4000, "ram_bytes": 8 * 1024**3, "gpu": 0},
    ]
    ng = {"node_count": 0, "vms": []}
    result = _select_flavor(pending, [], flavors, ng, headroom_factor=0.3)
    assert result is not None
    assert result["id"] == "small"  # 최소 적합 flavor


def test_select_flavor_no_fit():
    """모든 flavor가 너무 작으면 None 반환."""
    from app.services.k3s_stampede import _select_flavor

    pending = [{"resource_requests": {"cpu_m": 100_000, "memory_bytes": 1024**4, "gpu": 0}}]
    flavors = [{"id": "tiny", "name": "m1.tiny", "vcpus_m": 500, "ram_bytes": 512 * 1024**2, "gpu": 0}]
    ng = {"node_count": 0, "vms": []}
    result = _select_flavor(pending, [], flavors, ng, headroom_factor=0.3)
    assert result is None


def test_select_flavor_gpu_required():
    """GPU pod는 GPU flavor만 선택."""
    from app.services.k3s_stampede import _select_flavor

    pending = [{"resource_requests": {"cpu_m": 500, "memory_bytes": 512 * 1024**2, "gpu": 1}}]
    flavors = [
        {"id": "cpu", "name": "m1.cpu", "vcpus_m": 2000, "ram_bytes": 4 * 1024**3, "gpu": 0},
        {"id": "gpu", "name": "g1.gpu", "vcpus_m": 2000, "ram_bytes": 4 * 1024**3, "gpu": 1},
    ]
    ng = {"node_count": 0, "vms": []}
    result = _select_flavor(pending, [], flavors, ng, headroom_factor=0.3)
    assert result is not None
    assert result["id"] == "gpu"


# ---------------------------------------------------------------------------
# k3s_kube 파서 단위 테스트
# ---------------------------------------------------------------------------


def test_parse_cpu_millicores():
    from app.services.k3s_kube import _parse_cpu_millicores

    assert _parse_cpu_millicores("500m") == 500
    assert _parse_cpu_millicores("2") == 2000
    assert _parse_cpu_millicores("0.5") == 500
    assert _parse_cpu_millicores("") == 0


def test_parse_memory_bytes():
    from app.services.k3s_kube import _parse_memory_bytes

    assert _parse_memory_bytes("512Mi") == 512 * 1024**2
    assert _parse_memory_bytes("1Gi") == 1024**3
    assert _parse_memory_bytes("1024Ki") == 1024**2
    assert _parse_memory_bytes("") == 0


# ---------------------------------------------------------------------------
# Stampede API 엔드포인트 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stampede_enable_unauthenticated():
    """미인증 요청은 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/k3s/clusters/cl-1/stampede/enable")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stampede_enable_cluster_not_found(client):
    """클러스터 없으면 404."""
    with (
        patch("app.api.k3s.clusters.k3s_cluster") as mock_db,
        patch("app.api.k3s.clusters.get_settings") as mock_settings,
    ):
        mock_db.get_cluster = AsyncMock(return_value=None)
        s = MagicMock()
        s.k3s_stampede_enabled = True
        mock_settings.return_value = s
        resp = await client.post("/api/k3s/clusters/cl-1/stampede/enable")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stampede_enable_global_disabled(client):
    """전역 stampede_enabled=false면 400."""
    with (
        patch("app.api.k3s.clusters.k3s_cluster") as mock_db,
        patch("app.api.k3s.clusters.get_settings") as mock_settings,
    ):
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster())
        s = MagicMock()
        s.k3s_stampede_enabled = False
        mock_settings.return_value = s
        resp = await client.post("/api/k3s/clusters/cl-1/stampede/enable")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_stampede_disable_unauthenticated():
    """미인증 요청은 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/k3s/clusters/cl-1/stampede/disable")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stampede_status_unauthenticated():
    """미인증 요청은 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters/cl-1/stampede")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stampede_status_success(client):
    """Stampede 상태 조회 성공."""
    with (
        patch("app.api.k3s.clusters.k3s_cluster") as mock_db,
        patch("app.api.k3s.clusters.get_settings") as mock_settings,
        patch("app.services.k3s_nodegroup.list_nodegroups", new=AsyncMock(return_value=[_make_nodegroup()])),
    ):
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster())
        s = MagicMock()
        s.k3s_stampede_enabled = True
        mock_settings.return_value = s
        resp = await client.get("/api/k3s/clusters/cl-1/stampede")
    assert resp.status_code == 200
    data = resp.json()
    assert "stampede_enabled" in data
    assert "nodegroups" in data


# ---------------------------------------------------------------------------
# Stampede reconcile 루프 통합 테스트 (mock 기반)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_all_skips_when_disabled():
    """k3s_stampede_enabled=False면 아무것도 하지 않는다."""
    with patch("app.services.k3s_stampede.get_settings") as mock_s:
        s = MagicMock()
        s.k3s_stampede_enabled = False
        mock_s.return_value = s
        from app.services.k3s_stampede import run_all

        await run_all()  # 예외 없이 종료되어야 함


@pytest.mark.asyncio
async def test_run_all_no_active_clusters():
    """stampede_enabled 클러스터가 없으면 reconcile 실행 안 함."""
    with (
        patch("app.services.k3s_stampede.get_settings") as mock_s,
        patch("app.services.k3s_db.list_all_clusters", new=AsyncMock(return_value=[])),
    ):
        s = MagicMock()
        s.k3s_stampede_enabled = True
        mock_s.return_value = s
        from app.services.k3s_stampede import run_all

        await run_all()  # 예외 없이 종료되어야 함


@pytest.mark.asyncio
async def test_scale_up_respects_max_size():
    """node_count >= max_size면 scale-up을 하지 않는다."""
    from app.services.k3s_stampede import _scale_up_nodegroup

    ng = _make_nodegroup(node_count=3, max_size=3)
    pending = [
        {
            "resource_requests": {"cpu_m": 500, "memory_bytes": 256 * 1024**2, "gpu": 0},
            "node_selector": {},
            "tolerations": [],
            "affinity": {},
            "message": "Insufficient cpu",
        }
    ]

    with (
        patch("app.services.k3s_stampede.get_settings") as mock_s,
        patch("app.services.k3s_stampede._get_stampede_state", new=AsyncMock(return_value={})),
        patch("app.services.k3s_stampede._update_stampede_state", new=AsyncMock()),
        patch("app.services.k3s_stampede._get_available_flavors", new=AsyncMock(return_value=[])),
    ):
        s = MagicMock()
        s.k3s_stampede_scale_up_cooldown = 0
        s.k3s_stampede_resource_headroom_factor = 0.3
        mock_s.return_value = s
        # max_size 도달 → scale-up 없어야 함 (예외 없이 리턴)
        await _scale_up_nodegroup(
            cluster_id="cl-1",
            project_id="proj-1",
            nodegroup=ng,
            pending_pods=pending,
            node_pods=[],
            node_capacities=[],
            s=s,
        )


@pytest.mark.asyncio
async def test_scale_down_respects_min_size():
    """node_count <= min_size면 scale-down을 하지 않는다."""
    from app.services.k3s_stampede import _scale_down_nodegroup

    ng = _make_nodegroup(node_count=1, min_size=1)

    with patch("app.services.k3s_stampede._get_stampede_state", new=AsyncMock(return_value={})):
        s = MagicMock()
        s.k3s_stampede_scale_down_cooldown = 0
        s.k3s_stampede_scale_down_threshold = 0.5
        s.k3s_stampede_scale_down_window = 0
        s.k3s_stampede_interval = 60
        # min_size == node_count → 즉시 리턴 (예외 없이)
        await _scale_down_nodegroup(
            cluster_id="cl-1",
            project_id="proj-1",
            nodegroup=ng,
            node_pods=[],
            node_capacities=[],
            s=s,
        )


@pytest.mark.asyncio
async def test_reconcile_cluster_no_stampede_nodegroups():
    """stampede_enabled nodegroup이 없으면 K8s API 조회를 하지 않는다."""
    with (
        patch(
            "app.services.k3s_nodegroup.list_nodegroups",
            new=AsyncMock(return_value=[_make_nodegroup(stampede_enabled=False)]),
        ),
        patch("app.services.k3s_kube.list_unschedulable_pods") as mock_pods,
    ):
        from app.services.k3s_stampede import reconcile_cluster

        await reconcile_cluster(_make_cluster())
        mock_pods.assert_not_called()
