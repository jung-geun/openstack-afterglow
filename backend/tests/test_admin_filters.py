"""관리자 엔드포인트 필터 파라미터 단위 테스트 (volumes, instances, topology)."""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# all-volumes 필터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _make_volume(vid="v1", name="test-vol", status="available", project_id="proj-1"):
    v = MagicMock()
    v.id = vid
    v.name = name
    v.status = status
    v.size = 10
    v.project_id = project_id
    v.created_at = "2026-01-01T00:00:00Z"
    return v


@pytest.mark.asyncio
async def test_all_volumes_status_filter(admin_client, mock_conn):
    """status 파라미터가 Cinder SDK kwargs로 전달된다."""
    vol = _make_volume(status="available")
    mock_conn.block_storage.volumes.return_value = [vol]

    resp = await admin_client.get("/api/v1/admin/all-volumes?limit=10&status=available")
    assert resp.status_code == 200

    call_kwargs = mock_conn.block_storage.volumes.call_args[1]
    assert call_kwargs.get("status") == "available"


@pytest.mark.asyncio
async def test_all_volumes_project_id_filter(admin_client, mock_conn):
    """project_id 파라미터가 Cinder SDK kwargs로 전달된다."""
    vol = _make_volume(project_id="proj-abc")
    mock_conn.block_storage.volumes.return_value = [vol]

    resp = await admin_client.get("/api/v1/admin/all-volumes?limit=10&project_id=proj-abc")
    assert resp.status_code == 200

    call_kwargs = mock_conn.block_storage.volumes.call_args[1]
    assert call_kwargs.get("project_id") == "proj-abc"


@pytest.mark.asyncio
async def test_all_volumes_name_filter(admin_client, mock_conn):
    """name 파라미터가 name~ (substring) 키로 SDK에 전달된다."""
    vol = _make_volume(name="my-vol")
    mock_conn.block_storage.volumes.return_value = [vol]

    resp = await admin_client.get("/api/v1/admin/all-volumes?limit=10&name=my-vol")
    assert resp.status_code == 200

    call_kwargs = mock_conn.block_storage.volumes.call_args[1]
    assert call_kwargs.get("name~") == "my-vol"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# all-instances 필터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _make_servers_response(name="test-vm", status="ACTIVE", vid="inst-1"):
    return {
        "servers": [
            {
                "id": vid,
                "name": name,
                "status": status,
                "tenant_id": "proj-1",
                "user_id": "user-1",
                "flavor": {"original_name": "cpu.2c_4g"},
                "OS-EXT-SRV-ATTR:host": "compute1",
                "created": "2026-01-01T00:00:00Z",
            }
        ]
    }


def _make_session_response(data: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    return mock_resp


@pytest.mark.asyncio
async def test_all_instances_status_filter(admin_client, mock_conn):
    """status 파라미터가 Nova API params로 전달된다."""
    mock_conn.compute.get_endpoint.return_value = "http://nova"
    mock_conn.session.get.return_value = _make_session_response(_make_servers_response(status="ACTIVE"))

    resp = await admin_client.get("/api/v1/admin/all-instances?limit=10&status=ACTIVE")
    assert resp.status_code == 200

    call_kwargs = mock_conn.session.get.call_args[1]
    assert call_kwargs["params"].get("status") == "ACTIVE"


@pytest.mark.asyncio
async def test_all_instances_name_filter_wraps_in_regex(admin_client, mock_conn):
    """name 파라미터가 .*{re.escape(input)}.* 형태의 regex로 Nova에 전달된다."""
    mock_conn.compute.get_endpoint.return_value = "http://nova"
    mock_conn.session.get.return_value = _make_session_response(_make_servers_response(name="test-vm"))

    resp = await admin_client.get("/api/v1/admin/all-instances?limit=10&name=test-vm")
    assert resp.status_code == 200

    call_kwargs = mock_conn.session.get.call_args[1]
    name_param = call_kwargs["params"].get("name")
    assert name_param is not None
    expected = ".*" + re.escape("test-vm") + ".*"
    assert name_param == expected


@pytest.mark.asyncio
async def test_all_instances_name_filter_escapes_metachar(admin_client, mock_conn):
    """name 필터의 정규식 메타문자가 escape 처리된다."""
    mock_conn.compute.get_endpoint.return_value = "http://nova"
    mock_conn.session.get.return_value = _make_session_response({"servers": []})

    resp = await admin_client.get("/api/v1/admin/all-instances?limit=10&name=test.vm%5B")
    assert resp.status_code == 200

    call_kwargs = mock_conn.session.get.call_args[1]
    name_param = call_kwargs["params"].get("name")
    assert ".*" in name_param
    assert r"\." in name_param
    assert r"\[" in name_param


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# topology — instance.project_id 필드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.asyncio
async def test_topology_instance_includes_project_id(admin_client, mock_conn):
    """topology 응답의 instance 항목에 project_id 필드가 포함된다."""
    from app.models.storage import TopologyData

    mock_server = MagicMock()
    mock_server.id = "inst-1"
    mock_server.name = "my-vm"
    mock_server.status = "ACTIVE"
    mock_server.project_id = "proj-topo"
    mock_server.tenant_id = None
    mock_server.addresses = {}

    mock_conn.compute.servers.return_value = [mock_server]
    mock_conn.network.ports.return_value = []

    topo_data = TopologyData(networks=[], routers=[], instances=[], floating_ips=[])

    with (
        patch("app.api.identity.admin.neutron.get_topology", return_value=topo_data),
        patch("app.api.identity.admin.cached_call", new=AsyncMock(side_effect=lambda key, ttl, fn, **kw: fn())),
    ):
        resp = await admin_client.get("/api/v1/admin/topology")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["instances"]) == 1
    assert data["instances"][0]["project_id"] == "proj-topo"
