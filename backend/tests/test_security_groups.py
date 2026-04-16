"""보안그룹 API 단위 테스트."""

from unittest.mock import patch

import pytest


def make_sg(sg_id: str = "sg-1", name: str = "test-sg") -> dict:
    return {
        "id": sg_id,
        "name": name,
        "description": "test security group",
        "project_id": "test-project-123",
        "security_group_rules": [],
    }


@pytest.mark.asyncio
async def test_list_security_groups(client, mock_conn):
    async def mock_cached_call(key, ttl, fn, **kw):
        return fn()

    with (
        patch("app.api.network.security_groups.neutron.list_security_groups", return_value=[make_sg()]),
        patch("app.api.network.security_groups.cached_call", new=mock_cached_call),
    ):
        resp = await client.get("/api/security-groups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["id"] == "sg-1"


@pytest.mark.asyncio
async def test_create_security_group(client, mock_conn):
    with patch("app.api.network.security_groups.neutron.create_security_group", return_value=make_sg("sg-new")):
        resp = await client.post("/api/security-groups", json={"name": "test-sg", "description": "test"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_security_group(client, mock_conn):
    with patch("app.api.network.security_groups.neutron.delete_security_group", return_value=None):
        resp = await client.delete("/api/security-groups/sg-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_security_group_rule(client, mock_conn):
    rule = {"id": "rule-1", "direction": "ingress", "protocol": "tcp", "port_range_min": 22, "port_range_max": 22}
    with patch("app.api.network.security_groups.neutron.create_security_group_rule", return_value=rule):
        resp = await client.post(
            "/api/security-groups/sg-1/rules",
            json={
                "direction": "ingress",
                "protocol": "tcp",
                "port_range_min": 22,
                "port_range_max": 22,
            },
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_security_group_rule(client, mock_conn):
    with patch("app.api.network.security_groups.neutron.delete_security_group_rule", return_value=None):
        resp = await client.delete("/api/security-groups/sg-1/rules/rule-1")
    assert resp.status_code == 204
