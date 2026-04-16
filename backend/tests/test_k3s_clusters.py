"""k3s/clusters.py 엔드포인트 단위 테스트 (6개, k3s 서비스 필요)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_cluster_record():
    return {
        "id": "k3s-1",
        "name": "mycluster",
        "status": "ACTIVE",
        "status_reason": None,
        "server_vm_id": "vm-1",
        "agent_vm_ids": [],
        "agent_count": 0,
        "api_address": None,
        "server_ip": "10.0.0.1",
        "network_id": "net-1",
        "key_name": None,
        "k3s_version": "v1.31.4+k3s1",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_list_k3s_clusters_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_k3s_clusters_success(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.list_clusters = AsyncMock(return_value=[_make_cluster_record()])
        resp = await client.get("/api/k3s/clusters")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_k3s_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters/k3s-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_k3s_cluster_success(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        resp = await client.get("/api/k3s/clusters/k3s-1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_k3s_cluster_not_found(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=None)
        resp = await client.get("/api/k3s/clusters/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_kubeconfig_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_download_kubeconfig_not_ready(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        mock_db.get_kubeconfig = AsyncMock(return_value=None)
        resp = await client.get("/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_kubeconfig_success(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=_make_cluster_record())
        mock_db.get_kubeconfig = AsyncMock(return_value=b"apiVersion: v1\n...")
        resp = await client.get("/api/k3s/clusters/k3s-1/kubeconfig")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_scale_k3s_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.patch("/api/k3s/clusters/k3s-1/scale", json={"agent_count": 2})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scale_k3s_cluster_success(client):
    cluster = _make_cluster_record()
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=cluster)
        mock_db.update_cluster_status = AsyncMock()
        with patch("app.api.k3s.clusters.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock()
            resp = await client.patch("/api/k3s/clusters/k3s-1/scale", json={"agent_count": 0})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_k3s_cluster_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/k3s/clusters/k3s-1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_k3s_cluster_not_found(client):
    with patch("app.api.k3s.clusters.k3s_cluster") as mock_db:
        mock_db.get_cluster = AsyncMock(return_value=None)
        resp = await client.delete("/api/k3s/clusters/nonexistent")
    assert resp.status_code == 404
