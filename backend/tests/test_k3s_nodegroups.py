"""k3s 노드그룹 API 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest

_CLUSTER_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

_NG_SERVER = {
    "id": "ng-server-0000-1111-2222-333333333333",
    "cluster_id": _CLUSTER_ID,
    "name": "default-server",
    "role": "server",
    "node_count": 1,
    "flavor_id": "flavor-001",
    "image_id": None,
    "labels": {},
    "taints": [],
    "is_default": True,
    "vms": [],
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}

_NG_AGENT = {
    "id": "ng-agent-0000-1111-2222-333333333333",
    "cluster_id": _CLUSTER_ID,
    "name": "default-agent",
    "role": "agent",
    "node_count": 2,
    "flavor_id": "flavor-002",
    "image_id": None,
    "labels": {},
    "taints": [],
    "is_default": True,
    "vms": [{"vm_id": "vm-001", "name": "agent-1", "status": "RUNNING"}],
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}

_NG_CUSTOM = {
    "id": "ng-custom-0000-1111-2222-333333333333",
    "cluster_id": _CLUSTER_ID,
    "name": "gpu-workers",
    "role": "agent",
    "node_count": 3,
    "flavor_id": "flavor-gpu",
    "image_id": None,
    "labels": {"accelerator": "gpu"},
    "taints": [],
    "is_default": False,
    "vms": [],
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}

_CLUSTER = {
    "id": _CLUSTER_ID,
    "name": "test-cluster",
    "status": "RUNNING",
    "project_id": "test-project-123",
    "agent_vm_ids": ["vm-001"],
    "agent_count": 2,
}


def _cluster_access_ok():
    return patch("app.api.k3s.nodegroups.k3s_db.get_cluster", new=AsyncMock(return_value=_CLUSTER))


# ---------------------------------------------------------------------------
# 목록 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_nodegroups(client):
    with (
        _cluster_access_ok(),
        patch("app.services.k3s_nodegroup.list_nodegroups", new=AsyncMock(return_value=[_NG_SERVER, _NG_AGENT])),
    ):
        resp = await client.get(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "default-server"
    assert data[1]["name"] == "default-agent"


@pytest.mark.asyncio
async def test_list_nodegroups_cluster_not_found(client):
    with patch("app.api.k3s.nodegroups.k3s_db.get_cluster", new=AsyncMock(return_value=None)):
        resp = await client.get(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 단건 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_nodegroup(client):
    with _cluster_access_ok(), patch("app.services.k3s_nodegroup.get_nodegroup", new=AsyncMock(return_value=_NG_AGENT)):
        resp = await client.get(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/{_NG_AGENT['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "default-agent"
    assert resp.json()["node_count"] == 2


@pytest.mark.asyncio
async def test_get_nodegroup_not_found(client):
    with _cluster_access_ok(), patch("app.services.k3s_nodegroup.get_nodegroup", new=AsyncMock(return_value=None)):
        resp = await client.get(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_nodegroup_success(client):
    with (
        _cluster_access_ok(),
        patch("app.services.k3s_nodegroup.create_nodegroup", new=AsyncMock(return_value=_NG_CUSTOM)),
    ):
        resp = await client.post(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups",
            json={"name": "gpu-workers", "role": "agent", "node_count": 3, "flavor_id": "flavor-gpu"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "gpu-workers"
    assert data["node_count"] == 3
    assert data["is_default"] is False


@pytest.mark.asyncio
async def test_create_nodegroup_invalid_name(client):
    with _cluster_access_ok():
        resp = await client.post(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups",
            json={"name": "bad name!", "role": "agent", "node_count": 1},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_nodegroup_invalid_role(client):
    with _cluster_access_ok():
        resp = await client.post(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups",
            json={"name": "workers", "role": "master", "node_count": 1},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_nodegroup_duplicate_name(client):
    with (
        _cluster_access_ok(),
        patch(
            "app.services.k3s_nodegroup.create_nodegroup",
            new=AsyncMock(side_effect=ValueError("이미 같은 이름의 노드그룹이 존재합니다: default-agent")),
        ),
    ):
        resp = await client.post(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups",
            json={"name": "default-agent", "role": "agent", "node_count": 1},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_nodegroup_db_unavailable(client):
    with (
        _cluster_access_ok(),
        patch(
            "app.services.k3s_nodegroup.create_nodegroup",
            new=AsyncMock(side_effect=RuntimeError("DB가 설정되지 않아 노드그룹 기능을 사용할 수 없습니다.")),
        ),
    ):
        resp = await client.post(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups",
            json={"name": "workers", "role": "agent", "node_count": 1},
        )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 수정
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_nodegroup_node_count(client):
    updated = {**_NG_AGENT, "node_count": 5}
    with (
        _cluster_access_ok(),
        patch("app.services.k3s_nodegroup.update_nodegroup", new=AsyncMock(return_value=updated)),
    ):
        resp = await client.patch(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/{_NG_AGENT['id']}",
            json={"node_count": 5},
        )
    assert resp.status_code == 200
    assert resp.json()["node_count"] == 5


@pytest.mark.asyncio
async def test_update_nodegroup_not_found(client):
    with _cluster_access_ok(), patch("app.services.k3s_nodegroup.update_nodegroup", new=AsyncMock(return_value=None)):
        resp = await client.patch(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/nonexistent",
            json={"node_count": 3},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 삭제
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_custom_nodegroup(client):
    with _cluster_access_ok(), patch("app.services.k3s_nodegroup.delete_nodegroup", new=AsyncMock(return_value=True)):
        resp = await client.delete(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/{_NG_CUSTOM['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_default_nodegroup_rejected(client):
    with (
        _cluster_access_ok(),
        patch(
            "app.services.k3s_nodegroup.delete_nodegroup",
            new=AsyncMock(
                side_effect=ValueError("기본 노드그룹(default-server / default-agent)은 삭제할 수 없습니다.")
            ),
        ),
    ):
        resp = await client.delete(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/{_NG_AGENT['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_nodegroup_not_found(client):
    with _cluster_access_ok(), patch("app.services.k3s_nodegroup.delete_nodegroup", new=AsyncMock(return_value=False)):
        resp = await client.delete(f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# node_count 범위 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_nodegroup_node_count_too_large(client):
    with _cluster_access_ok():
        resp = await client.post(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups",
            json={"name": "big-group", "role": "agent", "node_count": 99},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_nodegroup_node_count_too_large(client):
    with _cluster_access_ok():
        resp = await client.patch(
            f"/api/v1/k3s/clusters/{_CLUSTER_ID}/nodegroups/{_NG_AGENT['id']}",
            json={"node_count": 99},
        )
    assert resp.status_code == 422
