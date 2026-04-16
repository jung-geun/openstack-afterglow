"""admin_flavors.py 엔드포인트 단위 테스트 (8개)."""
import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_list_admin_flavors_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/flavors")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_list_admin_flavors_allowed(admin_client, mock_conn):
    mock_conn.compute.flavors.return_value = iter([])
    resp = await admin_client.get("/api/admin/flavors")
    assert resp.status_code != 403

@pytest.mark.asyncio
async def test_create_flavor_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/flavors", json={
        "name": "m1.test", "vcpus": 1, "ram": 512, "disk": 10
    })
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_delete_flavor_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/flavors/flavor-1")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_list_flavor_access_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/flavors/flavor-1/access")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_set_extra_specs_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/flavors/flavor-1/extra-specs", json={"key": "val"})
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_delete_extra_spec_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/flavors/flavor-1/extra-specs/mykey")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_add_flavor_access_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/flavors/flavor-1/access", json={"project_id": "p"})
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_remove_flavor_access_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/flavors/flavor-1/access/proj-1")
    assert resp.status_code == 403
