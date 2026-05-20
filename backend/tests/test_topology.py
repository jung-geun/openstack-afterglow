"""Phase 53e — 토폴로지 서버측 project_id 필터링 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.storage import (
    TopologyData,
    TopologyNetwork,
    TopologyRouter,
)

PROJECT_A = "project-aaa"
PROJECT_B = "project-bbb"


def _make_server(sid: str, name: str, project_id: str, status: str = "ACTIVE"):
    s = MagicMock()
    s.id = sid
    s.name = name
    s.status = status
    s.project_id = project_id
    s.ip_addresses = []
    return s


def _make_topo(networks=None, routers=None):
    return TopologyData(
        networks=networks or [],
        routers=routers or [],
    )


def _patch_topology_deps(topo: TopologyData, servers: list):
    """neutron.get_topology, nova.list_servers, ports, get_topology_lbs를 한 번에 패치."""
    patches = [
        patch("app.api.network.networks.neutron.get_topology", return_value=topo),
        patch("app.api.network.networks.nova.list_servers", return_value=servers),
        patch("app.api.network.networks.get_topology_lbs", return_value=[]),
    ]
    return patches


def _apply(patches):
    for p in patches:
        p.start()
    return patches


def _stop(patches):
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# GET /api/networks/topology — user scope 필터링
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topology_filters_other_project_instances(client, mock_conn):
    """다른 프로젝트 인스턴스는 응답에 포함되지 않는다."""
    mock_conn._afterglow_project_id = PROJECT_A
    mock_conn.network.ports.return_value = []

    servers = [
        _make_server("s1", "vm-a", PROJECT_A),
        _make_server("s2", "vm-b", PROJECT_B),  # 다른 프로젝트
    ]
    topo = _make_topo()
    patches = _apply(_patch_topology_deps(topo, servers))

    try:
        from app.services import cache as cache_mod

        fake = MagicMock()
        fake.get = MagicMock(return_value=None)
        fake.setex = MagicMock(return_value=None)
        with patch.object(cache_mod, "_get_client", return_value=fake):
            resp = await client.get("/api/networks/topology")
    finally:
        _stop(patches)

    assert resp.status_code == 200
    data = resp.json()
    instance_ids = [i["id"] for i in data["instances"]]
    assert "s1" in instance_ids
    assert "s2" not in instance_ids


@pytest.mark.asyncio
async def test_topology_includes_external_networks(client, mock_conn):
    """external 네트워크는 다른 프로젝트 소유여도 포함된다."""
    mock_conn._afterglow_project_id = PROJECT_A
    mock_conn.network.ports.return_value = []

    ext_net = TopologyNetwork(
        id="net-ext",
        name="public",
        status="ACTIVE",
        is_external=True,
        is_shared=False,
        project_id=None,
    )
    priv_net = TopologyNetwork(
        id="net-prv",
        name="private-a",
        status="ACTIVE",
        is_external=False,
        is_shared=False,
        project_id=PROJECT_A,
    )
    other_net = TopologyNetwork(
        id="net-other",
        name="private-b",
        status="ACTIVE",
        is_external=False,
        is_shared=False,
        project_id=PROJECT_B,
    )

    topo = _make_topo(networks=[ext_net, priv_net, other_net])
    patches = _apply(_patch_topology_deps(topo, []))

    try:
        from app.services import cache as cache_mod

        fake = MagicMock()
        fake.get = MagicMock(return_value=None)
        fake.setex = MagicMock(return_value=None)
        with patch.object(cache_mod, "_get_client", return_value=fake):
            resp = await client.get("/api/networks/topology")
    finally:
        _stop(patches)

    assert resp.status_code == 200
    data = resp.json()
    net_ids = [n["id"] for n in data["networks"]]
    assert "net-ext" in net_ids  # external 포함
    assert "net-prv" in net_ids  # 자기 프로젝트 포함
    assert "net-other" not in net_ids  # 다른 프로젝트 private 제외


@pytest.mark.asyncio
async def test_topology_includes_shared_networks(client, mock_conn):
    """shared 네트워크는 다른 프로젝트 소유여도 포함된다."""
    mock_conn._afterglow_project_id = PROJECT_A
    mock_conn.network.ports.return_value = []

    shared_net = TopologyNetwork(
        id="net-shared",
        name="shared-net",
        status="ACTIVE",
        is_external=False,
        is_shared=True,
        project_id=PROJECT_B,
    )
    topo = _make_topo(networks=[shared_net])
    patches = _apply(_patch_topology_deps(topo, []))

    try:
        from app.services import cache as cache_mod

        fake = MagicMock()
        fake.get = MagicMock(return_value=None)
        fake.setex = MagicMock(return_value=None)
        with patch.object(cache_mod, "_get_client", return_value=fake):
            resp = await client.get("/api/networks/topology")
    finally:
        _stop(patches)

    assert resp.status_code == 200
    data = resp.json()
    net_ids = [n["id"] for n in data["networks"]]
    assert "net-shared" in net_ids


@pytest.mark.asyncio
async def test_topology_filters_other_project_routers(client, mock_conn):
    """다른 프로젝트 라우터는 user 토폴로지에서 제외된다."""
    mock_conn._afterglow_project_id = PROJECT_A
    mock_conn.network.ports.return_value = []

    router_a = TopologyRouter(
        id="r-a",
        name="router-a",
        status="ACTIVE",
        project_id=PROJECT_A,
    )
    router_b = TopologyRouter(
        id="r-b",
        name="router-b",
        status="ACTIVE",
        project_id=PROJECT_B,
    )
    topo = _make_topo(routers=[router_a, router_b])
    patches = _apply(_patch_topology_deps(topo, []))

    try:
        from app.services import cache as cache_mod

        fake = MagicMock()
        fake.get = MagicMock(return_value=None)
        fake.setex = MagicMock(return_value=None)
        with patch.object(cache_mod, "_get_client", return_value=fake):
            resp = await client.get("/api/networks/topology")
    finally:
        _stop(patches)

    assert resp.status_code == 200
    data = resp.json()
    router_ids = [r["id"] for r in data["routers"]]
    assert "r-a" in router_ids
    assert "r-b" not in router_ids


@pytest.mark.asyncio
async def test_topology_empty_project_returns_empty(client, mock_conn):
    """자기 프로젝트 자원이 없으면 인스턴스·라우터는 빈 목록."""
    mock_conn._afterglow_project_id = PROJECT_A
    mock_conn.network.ports.return_value = []

    servers = [_make_server("s1", "vm-b", PROJECT_B)]
    router_b = TopologyRouter(
        id="r-b",
        name="router-b",
        status="ACTIVE",
        project_id=PROJECT_B,
    )
    topo = _make_topo(routers=[router_b])
    patches = _apply(_patch_topology_deps(topo, servers))

    try:
        from app.services import cache as cache_mod

        fake = MagicMock()
        fake.get = MagicMock(return_value=None)
        fake.setex = MagicMock(return_value=None)
        with patch.object(cache_mod, "_get_client", return_value=fake):
            resp = await client.get("/api/networks/topology")
    finally:
        _stop(patches)

    assert resp.status_code == 200
    data = resp.json()
    assert data["instances"] == []
    assert data["routers"] == []
