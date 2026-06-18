"""Floating IP API 단위 테스트."""

from unittest.mock import patch

import pytest


def make_fip(fip_id: str = "fip-1", ip: str = "203.0.113.1") -> dict:
    return {
        "id": fip_id,
        "floating_ip_address": ip,
        "fixed_ip_address": None,
        "status": "DOWN",
        "port_id": None,
        "floating_network_id": "ext-net-1",
        "project_id": "test-project-123",
    }


@pytest.mark.asyncio
async def test_list_floating_ips(client, mock_conn):
    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    with (
        patch("app.api.network.networks.neutron.list_floating_ips", return_value=[make_fip()]),
        patch("app.api.network.networks.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/v1/networks/floating-ips")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["id"] == "fip-1"


@pytest.mark.asyncio
async def test_create_floating_ip(client, mock_conn):
    with patch("app.api.network.networks.neutron.create_floating_ip", return_value=make_fip("fip-new")):
        resp = await client.post("/api/v1/networks/floating-ips", json={"floating_network_id": "ext-net-1"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_associate_floating_ip(client, mock_conn):
    associated = make_fip()
    associated["port_id"] = "port-1"
    associated["fixed_ip_address"] = "192.168.1.10"
    with patch("app.api.network.networks.neutron.associate_floating_ip", return_value=associated):
        resp = await client.post("/api/v1/networks/floating-ips/fip-1/associate", json={"instance_id": "inst-1"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_disassociate_floating_ip(client, mock_conn):
    disassociated = make_fip()
    with patch("app.api.network.networks.neutron.disassociate_floating_ip", return_value=disassociated):
        resp = await client.post("/api/v1/networks/floating-ips/fip-1/disassociate")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_floating_ip(client, mock_conn):
    with patch("app.api.network.networks.neutron.delete_floating_ip", return_value=None):
        resp = await client.delete("/api/v1/networks/floating-ips/fip-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_floating_ips_with_instance(client, mock_conn):
    """port_id 가 있는 FIP 는 응답에 instance_id, instance_name 이 포함되어야 한다."""
    fip_with_instance = {
        **make_fip(),
        "port_id": "port-1",
        "fixed_ip_address": "192.168.1.10",
        "instance_id": "inst-1",
        "instance_name": "my-server",
    }

    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    with (
        patch("app.api.network.networks.neutron.list_floating_ips", return_value=[fip_with_instance]),
        patch("app.api.network.networks.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/v1/networks/floating-ips")

    assert resp.status_code == 200
    result = resp.json()[0]
    assert result["instance_id"] == "inst-1"
    assert result["instance_name"] == "my-server"


@pytest.mark.asyncio
async def test_list_floating_ips_without_instance(client, mock_conn):
    """port_id 가 없는 FIP 는 instance_id, instance_name 이 None 이어야 한다."""
    fip_unassociated = {
        **make_fip(),
        "instance_id": None,
        "instance_name": None,
    }

    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    with (
        patch("app.api.network.networks.neutron.list_floating_ips", return_value=[fip_unassociated]),
        patch("app.api.network.networks.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/v1/networks/floating-ips")

    assert resp.status_code == 200
    result = resp.json()[0]
    assert result["instance_id"] is None
    assert result["instance_name"] is None
