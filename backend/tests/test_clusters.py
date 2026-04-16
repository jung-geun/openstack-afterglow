"""container/clusters.py (Magnum) 엔드포인트 단위 테스트 (7개, Magnum 서비스 필요)."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.containers import ClusterInfo, ClusterTemplateInfo


def _make_cluster():
    return ClusterInfo(
        id="cl-1", name="mycluster", status="CREATE_COMPLETE",
        stack_id="stack-1", node_count=1, master_count=1,
        cluster_template_id="tmpl-1", keypair=None, create_timeout=60,
        api_address=None, master_addresses=[], node_addresses=[],
        created_at=None, updated_at=None,
    )


def _make_template():
    return ClusterTemplateInfo(
        id="tmpl-1", name="k8s-template", coe="kubernetes",
        image_id="img-1", flavor_id="flv-1", master_flavor_id="flv-1",
        dns_nameserver="8.8.8.8", docker_volume_size=None,
        network_driver="flannel", volume_driver=None,
        public=True, created_at=None,
    )


@pytest.mark.asyncio
async def test_list_clusters_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/clusters")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_clusters_success(client):
    with patch("app.api.container.clusters.asyncio") as mock_asyncio:
        mock_asyncio.wait_for = AsyncMock(return_value=[])
        resp = await client.get("/api/clusters")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_templates_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/clusters/templates")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_templates_success(client):
    with patch("app.api.container.clusters.asyncio") as mock_asyncio:
        mock_asyncio.wait_for = AsyncMock(return_value=[])
        resp = await client.get("/api/clusters/templates")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/clusters/cl-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_cluster_success(client):
    with patch("app.api.container.clusters.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=_make_cluster())
        resp = await client.get("/api/clusters/cl-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters", json={
            "name": "mycluster", "cluster_template_id": "tmpl-1",
            "node_count": 1, "master_count": 1,
        })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_cluster_success(client):
    with patch("app.api.container.clusters.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=_make_cluster())
        resp = await client.post("/api/clusters", json={
            "name": "mycluster", "cluster_template_id": "tmpl-1",
            "node_count": 1, "master_count": 1,
        })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/clusters/cl-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_cluster_success(client):
    with patch("app.api.container.clusters.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=None)
        resp = await client.delete("/api/clusters/cl-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_cluster_stack_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/clusters/cl-1/stack")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_cluster_stack_success(client):
    cluster = _make_cluster()
    stack_detail = {"id": "stack-1", "name": "k8s-stack", "status": "CREATE_COMPLETE", "resources": []}
    with patch("app.api.container.clusters.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(side_effect=[cluster, stack_detail])
        resp = await client.get("/api/clusters/cl-1/stack")
    assert resp.status_code == 200
