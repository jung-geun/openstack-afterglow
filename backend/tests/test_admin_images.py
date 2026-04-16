"""admin_images.py 엔드포인트 단위 테스트 (6개)."""
import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_list_admin_images_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/images")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_list_admin_images_allowed(admin_client, mock_conn):
    mock_conn.image.images.return_value = iter([])
    resp = await admin_client.get("/api/admin/images")
    assert resp.status_code != 403

@pytest.mark.asyncio
async def test_get_admin_image_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/images/img-1")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_patch_admin_image_requires_admin(non_admin_client):
    resp = await non_admin_client.patch("/api/admin/images/img-1", json={"name": "new"})
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_delete_admin_image_requires_admin(non_admin_client):
    resp = await non_admin_client.delete("/api/admin/images/img-1")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_deactivate_image_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/images/img-1/deactivate")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_reactivate_image_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/images/img-1/reactivate")
    assert resp.status_code == 403
