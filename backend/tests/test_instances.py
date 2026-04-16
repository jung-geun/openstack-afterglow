"""인스턴스 API 단위 테스트."""

from unittest.mock import patch

import pytest

from app.models.compute import InstanceInfo


def make_instance(instance_id: str = "inst-1", name: str = "test-vm", status: str = "ACTIVE") -> InstanceInfo:
    return InstanceInfo(
        id=instance_id,
        name=name,
        status=status,
        image_id="img-1",
        image_name="ubuntu-22.04",
        flavor_id="flavor-1",
        flavor_name="m1.small",
        ip_addresses=[],
        created_at="2024-01-01T00:00:00Z",
        metadata={},
        union_libraries=[],
        union_strategy=None,
        union_share_ids=[],
        union_upper_volume_id=None,
        key_name=None,
        user_id="test-user-123",
    )


# ────── GET 목록 & 상세 ──────


@pytest.mark.asyncio
async def test_list_instances(client, mock_conn):
    with (
        patch("app.api.compute.instances.nova.list_servers", return_value=[make_instance()]),
        patch("app.api.compute.instances.nova.list_flavors", return_value=[]),
        patch("app.api.compute.instances.glance.list_images", return_value=[]),
        patch("app.api.compute.instances.nova.list_volume_attachments", return_value=[]),
        patch("app.api.compute.instances.cinder.get_volume_image_metadata", return_value={}),
    ):
        resp = await client.get("/api/instances")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_instance(client, mock_conn):
    with (
        patch("app.api.compute.instances.nova.get_server", return_value=make_instance()),
        patch("app.api.compute.instances.nova.list_flavors", return_value=[]),
        patch("app.api.compute.instances.glance.list_images", return_value=[]),
    ):
        resp = await client.get("/api/instances/inst-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "inst-1"


# ────── DELETE ──────


@pytest.mark.asyncio
async def test_delete_instance(client, mock_conn):
    inst = make_instance()
    inst.metadata = {}
    with (
        patch("app.api.compute.instances.nova.get_server", return_value=inst),
        patch("app.api.compute.instances.nova.delete_server", return_value=None),
        patch("app.api.compute.instances.cinder.delete_volume", return_value=None),
    ):
        resp = await client.delete("/api/instances/inst-1")
    assert resp.status_code == 204


# ────── 라이프사이클 액션 ──────


@pytest.mark.asyncio
async def test_start_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.start_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/start")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_stop_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.stop_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/stop")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_reboot_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.reboot_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/reboot")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_shelve_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.shelve_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/shelve")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_unshelve_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.unshelve_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/unshelve")
    assert resp.status_code == 204


# ────── 콘솔/로그 ──────


@pytest.mark.asyncio
async def test_get_console(client, mock_conn):
    with patch("app.api.compute.instances.nova.get_console_url", return_value="https://console.example.com"):
        resp = await client.get("/api/instances/inst-1/console")
    assert resp.status_code == 200
    assert "url" in resp.json()


@pytest.mark.asyncio
async def test_get_console_log(client, mock_conn):
    with patch("app.api.compute.instances.nova.get_console_output", return_value="log output"):
        resp = await client.get("/api/instances/inst-1/log")
    assert resp.status_code == 200
    assert "output" in resp.json()


# ────── 볼륨 Attach/Detach ──────


@pytest.mark.asyncio
async def test_attach_volume(client, mock_conn):
    with patch("app.api.compute.instances.nova.attach_volume", return_value={"id": "attach-1", "volumeId": "vol-1"}):
        resp = await client.post("/api/instances/inst-1/volumes", json={"volume_id": "vol-1"})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_detach_volume(client, mock_conn):
    with patch("app.api.compute.instances.nova.detach_volume", return_value=None):
        resp = await client.delete("/api/instances/inst-1/volumes/vol-1")
    assert resp.status_code == 204


# ────── 인터페이스 Attach/Detach ──────


@pytest.mark.asyncio
async def test_attach_interface(client, mock_conn):
    with patch(
        "app.api.compute.instances.nova.attach_interface",
        return_value={"port_id": "port-1", "net_id": "net-1", "ip_address": "10.0.0.2"},
    ):
        resp = await client.post("/api/instances/inst-1/interfaces", json={"net_id": "net-1"})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_detach_interface(client, mock_conn):
    with patch("app.api.compute.instances.nova.detach_interface", return_value=None):
        resp = await client.delete("/api/instances/inst-1/interfaces/port-1")
    assert resp.status_code == 204


# ────── 입력 검증 ──────


@pytest.mark.asyncio
async def test_create_instance_invalid_name(client, mock_conn):
    """인스턴스 이름 regex 검증 — 특수문자 포함 시 422."""
    resp = await client.post(
        "/api/instances",
        json={
            "name": "invalid name!",
            "image_id": "img-1",
            "flavor_id": "flavor-1",
            "network_id": "net-1",
        },
    )
    assert resp.status_code == 422
