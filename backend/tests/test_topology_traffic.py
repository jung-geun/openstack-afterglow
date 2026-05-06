"""토폴로지 트래픽 엔드포인트 테스트."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PROJECT_ID = "test-project-123"

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _mock_port(
    device_id: str,
    network_id: str,
    device_owner: str = "compute:nova",
    port_id: str | None = None,
    mac_address: str | None = None,
):
    p = MagicMock()
    p.id = port_id or f"port-{device_id}"
    p.device_id = device_id
    p.device_owner = device_owner
    p.network_id = network_id
    p.mac_address = mac_address or "fa:16:3e:00:00:01"
    p.fixed_ips = [{"ip_address": "10.0.0.1", "subnet_id": "sub-1"}]
    return p


def _prom_instant_response(label_val_pairs: list[tuple[dict, float]]):
    """query_instant_multi 가 반환할 (labels, value) 리스트 생성."""
    return [(labels, val) for labels, val in label_val_pairs]


# ── 테스트: VM 트래픽 PromQL 매핑 ─────────────────────────────────────────────


@pytest.mark.anyio
async def test_traffic_returns_instances_from_promql(client, mock_conn):
    """node_exporter 결과에서 VM rx/tx bps 가 응답에 포함되고 byte→bit 변환(×8)이 적용돼야 한다."""
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address="fa:16:3e:00:00:01")
    ]

    rx_pairs = _prom_instant_response(
        [
            ({"instance_id": "uuid-1", "device": "ens3"}, 125_000.0),  # 125kB/s → 1Mbps
        ]
    )
    tx_pairs = _prom_instant_response(
        [
            ({"instance_id": "uuid-1", "device": "ens3"}, 62_500.0),  # 62.5kB/s → 500kbps
        ]
    )

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[rx_pairs, tx_pairs, [], []])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert "uuid-1" in body["instances"]
    inst = body["instances"]["uuid-1"]
    assert abs(inst["rx_bps"] - 1_000_000.0) < 1
    assert abs(inst["tx_bps"] - 500_000.0) < 1


@pytest.mark.anyio
async def test_traffic_aggregates_by_network(client, mock_conn):
    """같은 네트워크에 속한 VM 들의 bps 가 network 합산에 반영돼야 한다."""
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address="fa:16:3e:00:00:01"),
        _mock_port("uuid-2", "net-a", port_id="port-2", mac_address="fa:16:3e:00:00:02"),
    ]

    rx_pairs = _prom_instant_response(
        [
            ({"instance_id": "uuid-1", "device": "ens3"}, 100.0),
            ({"instance_id": "uuid-2", "device": "ens3"}, 200.0),
        ]
    )
    tx_pairs: list = []

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[rx_pairs, tx_pairs, [], []])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    net = body["networks"]["net-a"]
    assert abs(net["rx_bps"] - (100.0 + 200.0) * 8) < 1


@pytest.mark.anyio
async def test_traffic_routers_empty_with_meta(client, mock_conn):
    """routers 는 빈 dict, _meta.router_traffic 이 'exporter_required' 여야 한다."""
    mock_conn.network.ports.return_value = []

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(return_value=[])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert body["routers"] == {}
    assert body["_meta"]["router_traffic"] == "exporter_required"


@pytest.mark.anyio
async def test_traffic_handles_no_instances(client, mock_conn):
    """인스턴스 0개여도 200 OK 반환해야 한다."""
    mock_conn.network.ports.return_value = []

    with patch("app.api.network.networks.list_load_balancers", return_value=[]):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert body["instances"] == {}
    assert body["networks"] == {}


@pytest.mark.anyio
async def test_traffic_prom_unavailable_falls_back(client, mock_conn):
    """PromUnavailable 발생 시 instances={} 로 fallback — 전체 500 금지."""
    from app.services.prom_query import PromUnavailable

    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address="fa:16:3e:00:00:01")
    ]

    with (
        patch(
            "app.api.network.networks.query_instant_multi",
            new=AsyncMock(side_effect=PromUnavailable("timeout")),
        ),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    assert resp.json()["instances"] == {}


# ── 테스트: LB 차분 계산 ──────────────────────────────────────────────────────


def test_traffic_lb_first_call_zero():
    """최초 스냅샷 없을 때 lb_rate_from_snapshot 은 rx_bps=tx_bps=0 을 반환해야 한다."""
    from app.services import octavia

    octavia._lb_snapshot.clear()

    result = octavia.lb_rate_from_snapshot("lb-new", {"bytes_in": 1000, "bytes_out": 2000, "active_connections": 1})
    assert result["rx_bps"] == 0.0
    assert result["tx_bps"] == 0.0


def test_traffic_lb_rate_from_snapshot():
    """두 번째 호출에서 누적 차분으로 rate 를 계산해야 한다."""
    from app.services import octavia

    lb_id = "lb-rate-test"
    octavia._lb_snapshot.pop(lb_id, None)

    t0 = time.time() - 10  # 10초 전에 스냅샷이 있었다고 가정
    with octavia._snapshot_lock:
        octavia._lb_snapshot[lb_id] = (0, 0, t0)

    result = octavia.lb_rate_from_snapshot(
        lb_id, {"bytes_in": 1_250_000, "bytes_out": 2_500_000, "active_connections": 5}
    )
    # bytes_out 증분 2_500_000 bytes / 10s * 8 = 2_000_000 bps = 2 Mbps (rx)
    assert result["rx_bps"] > 0
    assert result["tx_bps"] > 0
    # bytes_in 증분 / 10s * 8: 1_250_000 / 10 * 8 = 1_000_000 bps
    assert abs(result["tx_bps"] - 1_000_000) < 50_000  # ±5% 허용 (타이밍)


# ── 테스트: query_instant_multi ───────────────────────────────────────────────


@pytest.mark.anyio
async def test_query_instant_multi_parses_results():
    """query_instant_multi 가 Prometheus JSON 에서 (labels, value) 리스트를 파싱해야 한다."""
    from unittest.mock import patch

    from app.services.prom_query import query_instant_multi

    fake_body = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"instance_id": "uuid-1"}, "value": [1700000000, "42.5"]},
                {"metric": {"instance_id": "uuid-2"}, "value": [1700000000, "10.0"]},
            ],
        },
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_body
    mock_resp.raise_for_status = MagicMock()

    async def _mock_get(*args, **kwargs):
        return mock_resp

    with patch("app.services.prom_query._get_client") as mock_client:
        mock_client.return_value.get = _mock_get
        result = await query_instant_multi('node_cpu_seconds_total{instance_id="uuid-1"}')

    assert len(result) == 2
    labels0, val0 = result[0]
    assert labels0["instance_id"] == "uuid-1"
    assert val0 == 42.5
    labels1, val1 = result[1]
    assert labels1["instance_id"] == "uuid-2"
    assert val1 == 10.0


# ── 테스트: libvirt-exporter MAC 기반 demux ───────────────────────────────────


@pytest.mark.anyio
async def test_traffic_libvirt_fills_missing_instances(client, mock_conn):
    """node_exporter 에 없는 인스턴스를 libvirt MAC 기반 경로로 채워야 한다."""
    MAC1 = "fa:16:3e:00:00:01"
    MAC2 = "fa:16:3e:00:00:02"
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address=MAC1),
        _mock_port("uuid-2", "net-a", port_id="port-2", mac_address=MAC2),
    ]

    # uuid-1 은 node_exporter 에만, uuid-2 는 libvirt 에만 있음
    ne_rx = _prom_instant_response([({"instance_id": "uuid-1", "device": "ens3"}, 100.0)])
    ne_tx: list = []
    lv_rx = _prom_instant_response([({"instance_id": "uuid-2", "mac_address": MAC2}, 200.0)])
    lv_tx = _prom_instant_response([({"instance_id": "uuid-2", "mac_address": MAC2}, 50.0)])

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[ne_rx, ne_tx, lv_rx, lv_tx])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert "uuid-1" in body["instances"]
    assert abs(body["instances"]["uuid-1"]["rx_bps"] - 100.0 * 8) < 1
    assert "uuid-2" in body["instances"]
    assert abs(body["instances"]["uuid-2"]["rx_bps"] - 200.0 * 8) < 1
    assert abs(body["instances"]["uuid-2"]["tx_bps"] - 50.0 * 8) < 1


@pytest.mark.anyio
async def test_traffic_libvirt_primary_node_exporter_supplements(client, mock_conn):
    """libvirt 가 주 경로(NIC demux). libvirt 미관측 인스턴스는 node_exporter 로 보강."""
    MAC1 = "fa:16:3e:00:00:01"
    MAC2 = "fa:16:3e:00:00:02"
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address=MAC1),
        _mock_port("uuid-2", "net-a", port_id="port-2", mac_address=MAC2),
    ]

    # uuid-1 은 libvirt + node_exporter 양쪽, uuid-2 는 node_exporter 만
    ne_rx = _prom_instant_response(
        [
            ({"instance_id": "uuid-1", "device": "ens3"}, 100.0),  # libvirt 값(200)에 밀려야 함
            ({"instance_id": "uuid-2", "device": "ens3"}, 50.0),  # libvirt 없으므로 보강
        ]
    )
    ne_tx = _prom_instant_response(
        [
            ({"instance_id": "uuid-2", "device": "ens3"}, 10.0),
        ]
    )
    lv_rx = _prom_instant_response([({"instance_id": "uuid-1", "mac_address": MAC1}, 200.0)])
    lv_tx = _prom_instant_response([({"instance_id": "uuid-1", "mac_address": MAC1}, 80.0)])

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[ne_rx, ne_tx, lv_rx, lv_tx])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    # uuid-1 은 libvirt 값 사용 (200 * 8)
    assert abs(body["instances"]["uuid-1"]["rx_bps"] - 200.0 * 8) < 1
    assert abs(body["instances"]["uuid-1"]["tx_bps"] - 80.0 * 8) < 1
    # uuid-2 는 node_exporter 보강 (50 * 8)
    assert abs(body["instances"]["uuid-2"]["rx_bps"] - 50.0 * 8) < 1
    assert abs(body["instances"]["uuid-2"]["tx_bps"] - 10.0 * 8) < 1


@pytest.mark.anyio
async def test_traffic_libvirt_query_uses_openstack_info_join(client, mock_conn):
    """libvirt PromQL 2개가 openstack_info 조인과 double group_left 패턴을 사용하는지 검증."""
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address="fa:16:3e:00:00:01")
    ]

    calls: list[str] = []

    async def _capture_query(promql: str):
        calls.append(promql)
        return []

    with (
        patch("app.api.network.networks.query_instant_multi", side_effect=_capture_query),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    assert len(calls) == 4
    lv_calls = [q for q in calls if "libvirt_domain_interface_stats_" in q]
    assert len(lv_calls) == 2
    for q in lv_calls:
        # 1단계 join: target_device 기준 mac_address 붙이기
        assert "* on (domain, target_device) group_left(mac_address)" in q
        assert "libvirt_domain_interface_stats_info" in q
        # 2단계 join: domain 기준 instance_id 붙이기
        assert "* on (domain) group_left(instance_id)" in q
        assert "libvirt_domain_openstack_info" in q


# ── 테스트: 멀티-NIC demux ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_traffic_multi_nic_demux(client, mock_conn):
    """멀티-NIC 인스턴스의 NIC 가 다른 네트워크에 각각 demux 돼야 한다."""
    MAC_A = "fa:16:3e:00:01:01"
    MAC_B = "fa:16:3e:00:01:02"
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-a1", mac_address=MAC_A),
        _mock_port("uuid-1", "net-b", port_id="port-b1", mac_address=MAC_B),
    ]

    lv_rx = _prom_instant_response(
        [
            ({"instance_id": "uuid-1", "mac_address": MAC_A}, 100.0),
            ({"instance_id": "uuid-1", "mac_address": MAC_B}, 200.0),
        ]
    )
    lv_tx = _prom_instant_response(
        [
            ({"instance_id": "uuid-1", "mac_address": MAC_A}, 10.0),
            ({"instance_id": "uuid-1", "mac_address": MAC_B}, 20.0),
        ]
    )

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[[], [], lv_rx, lv_tx])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()

    # interfaces 에 NIC 별로 2개 entry
    assert "port-a1" in body["interfaces"]
    assert "port-b1" in body["interfaces"]
    assert body["interfaces"]["port-a1"]["network_id"] == "net-a"
    assert body["interfaces"]["port-b1"]["network_id"] == "net-b"
    assert abs(body["interfaces"]["port-a1"]["rx_bps"] - 100.0 * 8) < 1
    assert abs(body["interfaces"]["port-b1"]["rx_bps"] - 200.0 * 8) < 1

    # instances 합산 = 두 NIC 합
    assert abs(body["instances"]["uuid-1"]["rx_bps"] - (100.0 + 200.0) * 8) < 1

    # networks 가 NIC 단위로 분리
    assert abs(body["networks"]["net-a"]["rx_bps"] - 100.0 * 8) < 1
    assert abs(body["networks"]["net-b"]["rx_bps"] - 200.0 * 8) < 1


@pytest.mark.anyio
async def test_traffic_node_exporter_supplements_single_nic_to_networks(client, mock_conn):
    """single-NIC 인스턴스가 libvirt 에 없고 node_exporter 에만 있으면 networks 에도 합산돼야 한다."""
    MAC1 = "fa:16:3e:00:00:01"
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address=MAC1),
    ]

    ne_rx = _prom_instant_response([({"instance_id": "uuid-1", "device": "ens3"}, 100.0)])
    ne_tx: list = []

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[ne_rx, ne_tx, [], []])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert "uuid-1" in body["instances"]
    assert abs(body["instances"]["uuid-1"]["rx_bps"] - 100.0 * 8) < 1
    # single-NIC 이므로 networks 에도 합산
    assert "net-a" in body["networks"]
    assert abs(body["networks"]["net-a"]["rx_bps"] - 100.0 * 8) < 1


@pytest.mark.anyio
async def test_traffic_node_exporter_multi_nic_skips_networks_aggregation(client, mock_conn):
    """multi-NIC 인스턴스가 libvirt 에 미관측이면 instances 는 채우되 networks 합산은 스킵해야 한다."""
    MAC_A = "fa:16:3e:00:01:01"
    MAC_B = "fa:16:3e:00:01:02"
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-a1", mac_address=MAC_A),
        _mock_port("uuid-1", "net-b", port_id="port-b1", mac_address=MAC_B),
    ]

    ne_rx = _prom_instant_response([({"instance_id": "uuid-1", "device": "ens3"}, 300.0)])
    ne_tx: list = []

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[ne_rx, ne_tx, [], []])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    # instances 는 채워져야 함
    assert "uuid-1" in body["instances"]
    assert abs(body["instances"]["uuid-1"]["rx_bps"] - 300.0 * 8) < 1
    # multi-NIC 이므로 귀속 불명 → networks 에 합산 없음
    assert "net-a" not in body["networks"]
    assert "net-b" not in body["networks"]


@pytest.mark.anyio
async def test_traffic_new_attach_within_libvirt_scrape_window(client, mock_conn):
    """attach 직후 libvirt 미스크레이프 윈도: port_map 에는 등장하되 libvirt 결과 비었을 때 200 OK."""
    MAC1 = "fa:16:3e:00:00:01"
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address=MAC1),
    ]

    # libvirt 가 아직 스크레이프 못 한 상태 (lv_rx, lv_tx 모두 빈 리스트)
    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[[], [], [], []])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    # 에러가 아닌 빈 dict 또는 rx/tx=0 으로 처리됨
    assert isinstance(body["instances"], dict)
    if "uuid-1" in body["instances"]:
        assert body["instances"]["uuid-1"]["rx_bps"] == 0.0
    assert "port-1" not in body["interfaces"]


@pytest.mark.anyio
async def test_traffic_libvirt_promql_uses_double_group_left(client, mock_conn):
    """libvirt PromQL 에 mac_address 조인과 instance_id 조인이 모두 포함돼야 한다."""
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a", port_id="port-1", mac_address="fa:16:3e:00:00:01")
    ]

    calls: list[str] = []

    async def _capture_query(promql: str):
        calls.append(promql)
        return []

    with (
        patch("app.api.network.networks.query_instant_multi", side_effect=_capture_query),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        await client.get("/api/networks/topology/traffic")

    lv_calls = [
        q
        for q in calls
        if "libvirt_domain_interface_stats_receive_bytes_total" in q
        or "libvirt_domain_interface_stats_transmit_bytes_total" in q
    ]
    assert len(lv_calls) == 2
    for q in lv_calls:
        assert "* on (domain, target_device) group_left(mac_address)" in q
        assert "* on (domain) group_left(instance_id)" in q
