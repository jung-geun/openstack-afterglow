"""이미지 API 테스트."""

from unittest.mock import patch

import pytest

from app.models.compute import ImageInfo


def make_image(owner: str = "test-project-123") -> ImageInfo:
    return ImageInfo(
        id="img-1",
        name="ubuntu-22.04",
        status="active",
        size=2_000_000_000,
        min_disk=20,
        min_ram=0,
        disk_format="qcow2",
        os_distro="ubuntu",
        created_at="2024-01-01T00:00:00",
        owner=owner,
    )


@pytest.mark.asyncio
async def test_list_images(client, mock_conn):
    with patch("app.api.compute.images.glance.list_images", return_value=[make_image()]):

        async def mock_cached_call(key, ttl, fn, **kw):
            return fn()

        with patch("app.api.compute.images.cached_call", new=mock_cached_call):
            resp = await client.get("/api/images")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["os_distro"] == "ubuntu"
    assert data[0]["owner"] == "test-project-123"


@pytest.mark.asyncio
async def test_update_image_metadata(client, mock_conn):
    updated = make_image()
    updated.name = "ubuntu-22.04-updated"
    with patch("app.api.compute.images.glance.update_image_metadata", return_value=updated):
        resp = await client.patch("/api/images/img-1", json={"name": "ubuntu-22.04-updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "ubuntu-22.04-updated"
